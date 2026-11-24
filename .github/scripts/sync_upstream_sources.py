#!/usr/bin/env python3
"""Copy immutable upstream Flatpak inputs; never execute or check out PR code."""

import argparse
import base64
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml

APPLICATION_URL = 'https://github.com/agalwood/Motrix.git'
UPSTREAM_REPO = 'agalwood/Motrix'
MANIFEST = 'net.agalwood.Motrix.yml'
RECIPE = 'flatpak/app.motrix.native.yml'
SOURCE_LISTS = ('generated-sources.json', 'cargo-sources.json')
SHA = re.compile(r'[0-9a-f]{40}')
STABLE_TAG = re.compile(r'v[0-9]+\.[0-9]+\.[0-9]+')
MAX_RESPONSE = 32 * 1024 * 1024
UPDATE_BOTS = {'flathubbot'}

METADATA_REWRITE = r'''set -eu
desktop="$FLATPAK_DEST/share/applications/$FLATPAK_ID.desktop"
metainfo="$FLATPAK_DEST/share/metainfo/$FLATPAK_ID.metainfo.xml"
test "$(grep -Fxc 'Icon=app.motrix.native' "$desktop")" = 1
test "$(grep -Fxc '  <id>app.motrix.native</id>' "$metainfo")" = 1
test "$(grep -Fxc '  <launchable type="desktop-id">app.motrix.native.desktop</launchable>' "$metainfo")" = 1
sed -i 's/^Icon=app\.motrix\.native$/Icon=net.agalwood.Motrix/' "$desktop"
sed -i 's|^  <id>app\.motrix\.native</id>$|  <id>net.agalwood.Motrix</id>|; s|^  <launchable type="desktop-id">app\.motrix\.native\.desktop</launchable>$|  <launchable type="desktop-id">net.agalwood.Motrix.desktop</launchable>|' "$metainfo"
'''


class SyncError(ValueError):
    """A failed safety or consistency precondition."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SyncError('HTTP redirects are not accepted; check repository identity')


class UniqueSafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            if not isinstance(key_node, yaml.ScalarNode):
                raise SyncError('YAML mapping keys must be scalars')
            key = self.construct_object(key_node, deep=deep)
            if key in result:
                raise SyncError(f'Duplicate YAML key: {key}')
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def load_manifest(payload):
    if len(payload) > 512 * 1024:
        raise SyncError('Manifest exceeds 512 KiB')
    if any(isinstance(token, (yaml.AliasToken, yaml.AnchorToken)) for token in yaml.scan(payload)):
        raise SyncError('YAML aliases/anchors require manual review')
    result = yaml.load(payload, Loader=UniqueSafeLoader)
    if not isinstance(result, dict):
        raise SyncError('Manifest must be a mapping')
    return result


def checked_sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise SyncError('Expected a 40-character lowercase commit SHA')
    return value


def application_source(manifest: dict) -> dict:
    modules = manifest.get('modules', [])
    matches = [m for m in modules if isinstance(m, dict) and m.get('name') == 'motrix']
    if len(matches) != 1:
        raise SyncError('Expected exactly one motrix module')
    sources = [s for s in matches[0].get('sources', []) if isinstance(s, dict)
               and s.get('type') == 'git' and s.get('url') == APPLICATION_URL]
    if len(sources) != 1:
        raise SyncError('Expected one motrix git source at the fixed HTTPS Motrix URL')
    source = sources[0]
    if not isinstance(source.get('tag'), str) or not STABLE_TAG.fullmatch(source['tag']):
        raise SyncError('Application tag must be a stable vN.N.N release')
    checked_sha(source.get('commit'))
    return source


def adapt_manifest(upstream: dict, source: dict) -> dict:
    """The exhaustive downstream delta; all other recipe fields are retained."""
    result = copy.deepcopy(upstream)
    if result.get('app-id') != 'app.motrix.native':
        raise SyncError('Unexpected upstream application identity')
    result['app-id'] = 'net.agalwood.Motrix'
    modules = result.get('modules', [])
    apps = [m for m in modules if isinstance(m, dict) and m.get('name') == 'motrix']
    engines = [m for m in modules if isinstance(m, dict) and m.get('name') == 'aria2']
    if len(apps) != 1 or len(engines) != 1:
        raise SyncError('Expected unique motrix and aria2 modules')
    app, engine = apps[0], engines[0]
    placeholder = {
        'type': 'git', 'url': 'https://github.com/TODO-ORG/motrix-turbo.git',
        'tag': 'TODO-RELEASE-TAG', 'commit': 'TODO-RELEASE-COMMIT-SHA',
        'x-checker-data': {'type': 'git', 'tag-pattern': r'^v([\d.]+)$'},
    }
    sources = app['sources']
    if sources.count(placeholder) != 1:
        raise SyncError('Unexpected upstream application source shape; review adaptation')
    index = sources.index(placeholder)
    replacement = {
        'type': 'git', 'url': APPLICATION_URL, 'tag': source['tag'], 'commit': source['commit'],
        'x-checker-data': {'type': 'git', 'tag-pattern': r'^v([0-9]+\.[0-9]+\.[0-9]+)$'},
    }
    # Reuse input validation without normalizing away any local manifest fields.
    application_source({'modules': [{'name': 'motrix', 'sources': [replacement]}]})
    sources[index:index + 1] = [replacement, {'type': 'patch', 'path': 'patches/retain-flathub-id.patch'}]
    engine_sources = [s for s in engine['sources'] if isinstance(s, dict) and s.get('type') == 'git'
                      and s.get('url') == 'https://github.com/motrixapp/aria2.git']
    if len(engine_sources) != 1 or 'x-checker-data' not in engine_sources[0]:
        raise SyncError('Unexpected upstream aria2 source/checker shape')
    del engine_sources[0]['x-checker-data']
    for name in ('app.motrix.native.metainfo.xml', 'app.motrix.native.desktop'):
        item = {'type': 'file', 'path': name}
        if sources.count(item) != 1:
            raise SyncError(f'Unexpected upstream metadata source: {name}')
        sources.remove(item)
        directory = 'metainfo' if name.endswith('.xml') else 'applications'
        suffix = 'metainfo.xml' if name.endswith('.xml') else 'desktop'
        old = f'install -Dm644 {name} $FLATPAK_DEST/share/{directory}/$FLATPAK_ID.{suffix}'
        if app['build-commands'].count(old) != 1:
            raise SyncError(f'Unexpected metadata install command: {name}')
        i = app['build-commands'].index(old)
        app['build-commands'][i] = old.replace(f' {name} ', f' flatpak/{name} ')
    desktop_install = 'install -Dm644 flatpak/app.motrix.native.desktop $FLATPAK_DEST/share/applications/$FLATPAK_ID.desktop'
    app['build-commands'].insert(app['build-commands'].index(desktop_install) + 1, METADATA_REWRITE)
    for name in SOURCE_LISTS:
        if sources.count(name) != 1:
            raise SyncError(f'Expected exactly one local source include: {name}')
    return result


def reject_constant(value):
    raise SyncError(f'Non-JSON numeric constant: {value}')


def validate_source_list(payload: bytes) -> list:
    if len(payload) > MAX_RESPONSE:
        raise SyncError('Source list exceeds response size limit')
    value = json.loads(payload, parse_constant=reject_constant)
    if not isinstance(value, list) or not value or not all(
        isinstance(item, dict) and isinstance(item.get('type'), str) for item in value
    ):
        raise SyncError('Expected a nonempty JSON array of Flatpak source objects')
    return value


def git_blob_sha(payload):
    return hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()


def report(message):
    print(message)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as stream:
            stream.write(message + '\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--pr', required=True)
    parser.add_argument('--reviewed-recipe-sha256')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    try:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+', args.repository):
            raise SyncError('Repository must be OWNER/REPO, not a URL')
        if not re.fullmatch(r'[1-9][0-9]*', args.pr):
            raise SyncError('PR must be a positive integer')
        if os.environ.get('GITHUB_REPOSITORY', args.repository).lower() != args.repository.lower():
            raise SyncError('Repository does not match the workflow repository')
        if args.reviewed_recipe_sha256:
            if os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch':
                raise SyncError('Recipe review digest is accepted only on workflow_dispatch')
            if not re.fullmatch(r'[0-9a-f]{64}', args.reviewed_recipe_sha256):
                raise SyncError('Review digest must be a lowercase SHA256')
        token = os.environ.get('GH_TOKEN')
        if not token:
            raise SyncError('Set GH_TOKEN for repository API access')
        opener = build_opener(NoRedirect())
        repo_path = '/repos/' + args.repository

        def request(url, data=None, method='GET', missing_ok=False):
            headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'motrix-source-sync'}
            if url.startswith('https://api.github.com/'):
                headers.update({'Authorization': 'Bearer ' + token, 'X-GitHub-Api-Version': '2022-11-28'})
            body = None if data is None else json.dumps(data).encode()
            if body is not None:
                headers['Content-Type'] = 'application/json'
            try:
                with opener.open(Request(url, data=body, headers=headers, method=method), timeout=30) as response:
                    payload = response.read(MAX_RESPONSE + 1)
            except HTTPError as error:
                if missing_ok and error.code == 404:
                    return None
                raise SyncError(f'HTTP {error.code} fetching {url}; retry after checking access/head') from error
            if len(payload) > MAX_RESPONSE:
                raise SyncError(f'Response too large: {url}')
            return payload

        def api(path, data=None, method='GET'):
            return json.loads(request('https://api.github.com' + path, data, method))

        def upstream(commit, path, missing_ok=False):
            checked_sha(commit)
            return request(f'https://raw.githubusercontent.com/{UPSTREAM_REPO}/{commit}/{path}', missing_ok=missing_ok)

        default_branch = api(repo_path)['default_branch']

        def trusted_pr():
            pr = api(f'{repo_path}/pulls/{args.pr}')
            if (pr['state'] != 'open' or pr['head'].get('repo') is None
                    or pr['head']['repo']['full_name'].lower() != args.repository.lower()
                    or pr['base']['repo']['full_name'].lower() != args.repository.lower()
                    or pr['base']['ref'] != default_branch):
                raise SyncError('Require an open same-repository PR targeting the default branch; retry on a trusted PR')
            login = pr['user']['login']
            if login not in UPDATE_BOTS:
                permission = api(f'{repo_path}/collaborators/{quote(login, safe="")}/permission')['permission']
                if permission not in {'write', 'maintain', 'admin'}:
                    raise SyncError('PR author is not an allowlisted update bot or a write collaborator')
            checked_sha(pr['head']['sha'])
            checked_sha(pr['base']['sha'])
            return pr

        pr = trusted_pr()
        head = pr['head']['sha']

        def manifest_at(commit):
            item = api(f'{repo_path}/contents/{MANIFEST}?ref={checked_sha(commit)}')
            if item.get('type') != 'file' or item.get('encoding') != 'base64':
                raise SyncError('Manifest must be a regular, base64-encoded repository file')
            return load_manifest(base64.b64decode(item['content'].replace('\n', ''), validate=True))

        candidate = manifest_at(head)
        source = application_source(candidate)
        old_source = application_source(manifest_at(pr['base']['sha']))
        tag = api(f'/repos/{UPSTREAM_REPO}/git/ref/tags/{source["tag"]}')['object']
        for _ in range(8):
            checked_sha(tag['sha'])
            if tag['type'] == 'commit':
                break
            if tag['type'] != 'tag':
                raise SyncError('Release tag does not reference a commit')
            tag = api(f'/repos/{UPSTREAM_REPO}/git/tags/{tag["sha"]}')['object']
        if tag['type'] != 'commit' or tag['sha'] != source['commit']:
            raise SyncError('Manifest commit does not match the peeled release tag')

        new_recipe = upstream(source['commit'], RECIPE)
        old_recipe = upstream(old_source['commit'], RECIPE, missing_ok=True)
        digest = hashlib.sha256(new_recipe).hexdigest()
        if args.reviewed_recipe_sha256 and args.reviewed_recipe_sha256 != digest:
            raise SyncError('Reviewed recipe SHA256 does not match retrieved immutable bytes')
        if old_recipe is None or old_recipe != new_recipe:
            diff = ''.join(difflib.unified_diff(
                (old_recipe or b'').decode().splitlines(keepends=True),
                new_recipe.decode().splitlines(keepends=True),
                fromfile=old_source['commit'] + '/' + RECIPE,
                tofile=source['commit'] + '/' + RECIPE,
            ))
            heading = 'Review-required bootstrap: old release has no Flatpak recipe' if old_recipe is None else 'Upstream recipe drift requires review'
            # An extra-long fence prevents upstream text from closing the diff block.
            fence = '`' * (max((len(x) for x in re.findall(r'`+', diff)), default=2) + 1)
            report(f'## {heading}\n\nNew recipe SHA256: `{digest}`\n\n{fence}diff\n{diff}\n{fence}')
            if args.reviewed_recipe_sha256 != digest:
                raise SyncError('Review recipe diff, update the PR adaptation, then manually dispatch with its exact SHA256')
        if candidate != adapt_manifest(load_manifest(new_recipe), source):
            raise SyncError('PR manifest differs from the complete adapted upstream recipe; update it before synchronizing')
        payloads = {name: upstream(source['commit'], 'flatpak/' + name) for name in SOURCE_LISTS}
        for payload in payloads.values():
            validate_source_list(payload)

        parent = api(f'{repo_path}/git/commits/{head}')
        tree_sha = checked_sha(parent['tree']['sha'])
        tree = api(f'{repo_path}/git/trees/{tree_sha}')
        if tree.get('truncated'):
            raise SyncError('Truncated PR tree; refusing an incomplete comparison')
        entries = {item['path']: item for item in tree['tree']}
        if all(entries.get(name, {}).get('type') == 'blob'
               and entries[name].get('mode') == '100644'
               and entries[name].get('sha') == git_blob_sha(payloads[name]) for name in SOURCE_LISTS):
            report(f'No changes: both source lists already match {source["commit"]} at PR head {head}.')
            return 0
        if not args.write:
            report(f'Check passed at {head}; both validated source lists would be synchronized (no writes).')
            return 0

        latest = trusted_pr()
        if latest['head']['sha'] != head or latest['head']['ref'] != pr['head']['ref'] or latest['base']['sha'] != pr['base']['sha']:
            raise SyncError('PR changed during synchronization; no ref update made, retry against the new head')
        # A non-forced REST ref update is not compare-and-swap: a concurrent
        # rewind to an ancestor would still permit a fast-forward restoring H.
        # This mutation atomically checks H, creates its child and updates the ref.
        mutation = '''mutation SyncSources($input: CreateCommitOnBranchInput!) {
          createCommitOnBranch(input: $input) { commit { oid } }
        }'''
        result = api('/graphql', {
            'query': mutation,
            'variables': {'input': {
                'branch': {'repositoryNameWithOwner': args.repository, 'branchName': pr['head']['ref']},
                'expectedHeadOid': head,
                'message': {'headline': f'build: sync upstream offline sources for {source["tag"]}'},
                'fileChanges': {'additions': [
                    {'path': name, 'contents': base64.b64encode(payloads[name]).decode()}
                    for name in SOURCE_LISTS
                ]},
            }},
        }, 'POST')
        if result.get('errors'):
            raise SyncError('Atomic commit refused (head changed or repository policy denied it); review current head and retry')
        new_head = checked_sha(result['data']['createCommitOnBranch']['commit']['oid'])
        report(f'Synchronized only the two source lists at `{new_head}`. Request Flathub validation of this exact head before merge.')
        return 0
    except (ValueError, KeyError, TypeError, OSError, URLError, yaml.YAMLError, RecursionError) as error:
        print(f'Source sync refused: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
