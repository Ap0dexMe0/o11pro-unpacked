#!/usr/bin/env python3
"""Scan provider .cfg files and generate cache/orig_urls.json for HLS proxy.

Usage:
    python3 generate_orig_urls.py
    python3 generate_orig_urls.py --dir ./providers  (custom provider dir)
    python3 generate_orig_urls.py --output ./cache/orig_urls.json
"""
import json
import os
import sys
import glob
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
DEFAULT_PROVIDERS_DIR = os.path.join(PROJECT_DIR, 'providers')
DEFAULT_OUTPUT = os.path.join(PROJECT_DIR, 'cache', 'orig_urls.json')

HLS_OUTPUT_MODES = {'directhls', 'hls', 'hlsts', 'hlsfmp4'}
HLS_RUNNING_MODES = {'internalremuxer', 'hls'}

def find_cfg_files(providers_dir):
    if not os.path.isdir(providers_dir):
        return []
    return glob.glob(os.path.join(providers_dir, '*.cfg'))

def extract_hls_streams(cfg_path):
    try:
        with open(cfg_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f'  SKIP: {os.path.basename(cfg_path)} parse error: {e}', file=sys.stderr)
        return []

    streams = []
    provider_name = data.get('Name', os.path.splitext(os.path.basename(cfg_path))[0])

    # Check if this provider is HLS-capable
    output_mode = data.get('OutputMode', '')
    running_mode = data.get('RunningMode', '')

    for s in data.get('Streams', []):
        manifest = s.get('Manifest', '')
        if not manifest:
            continue

        # Determine if stream is HLS — check OutputMode, RunningMode, or manifest URL
        stream_output = s.get('OutputMode', output_mode)
        stream_running = s.get('RunningMode', running_mode)
        is_hls = (
            stream_output.lower() in HLS_OUTPUT_MODES
            or stream_running.lower() in HLS_RUNNING_MODES
            or '.m3u8' in manifest.lower()
        )
        if not is_hls:
            continue

        name = s.get('Name', '').strip()
        if not name:
            continue

        # Check for auth params
        auth = None
        script_user = s.get('ScriptAccountsUser', '')
        script_params = s.get('ScriptParams', '')
        if script_user and script_params and ':' in script_params:
            parts = script_params.split()
            for p in parts:
                if ':' in p and not p.startswith('-'):
                    auth = p.split(':', 1)
                    break

        streams.append({
            'name': name,
            'url': manifest,
            'auth': auth,
            'provider': provider_name,
        })

    return streams

def generate(providers_dir, output_path):
    cfg_files = find_cfg_files(providers_dir)

    if not cfg_files:
        print(f'No .cfg files found in {providers_dir}')
        print('Providers directory will be created at runtime by RunMe.sh')
        return False

    all_streams = []
    for path in sorted(cfg_files):
        streams = extract_hls_streams(path)
        if streams:
            all_streams.extend(streams)
            print(f'  {os.path.basename(path)}: {len(streams)} HLS streams')

    if not all_streams:
        print('No HLS streams found in any config files')
        return False

    # Build the output map
    channel_map = {}
    for s in all_streams:
        if s['auth']:
            channel_map[s['name']] = {
                'url': s['url'],
                'auth': s['auth']
            }
        else:
            channel_map[s['name']] = s['url']

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(channel_map, f, indent=2, ensure_ascii=False)

    print(f'\nGenerated {len(channel_map)} channels -> {output_path}')
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate orig_urls.json for HLS proxy from provider .cfg files')
    parser.add_argument('--dir', default=DEFAULT_PROVIDERS_DIR,
                        help=f'Provider configs directory (default: {DEFAULT_PROVIDERS_DIR})')
    parser.add_argument('--output', default=DEFAULT_OUTPUT,
                        help=f'Output path (default: {DEFAULT_OUTPUT})')
    args = parser.parse_args()

    print(f'Providers dir: {args.dir}')
    print(f'Output:        {args.output}')
    print()
    success = generate(args.dir, args.output)
    if not success:
        print('\nTip: place .cfg provider files in the providers/ directory and re-run')
        sys.exit(1)
