import os
import subprocess
import argparse
import yaml

def is_cygwin():
    ostype = os.getenv('OSTYPE', '').lower()
    return 'cygwin' in ostype

def cygwin_to_windows_path(cygwin_path):
    result = subprocess.run(['cygpath', '-w', cygwin_path], capture_output=True, text=True)
    return result.stdout.strip()

def ensure_windows_path(path):
    if is_cygwin():
        return cygwin_to_windows_path(path)
    else:
        return os.path.abspath(path)

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Image Sorter Configuration")
    parser.add_argument('--config', type=str, help="Path to the YAML configuration file")
    parser.add_argument('--categories', type=str, nargs='*', default=['Sorted'], help="List of categories")
    parser.add_argument('--base_dir', type=str, default='.', help="Base directory for category folders")
    return parser.parse_args(args)

def read_config_file(config_path):
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def get_configuration():
    args = parse_args()

    if args.config:
        config = read_config_file(args.config)
        categories = config.get('categories', ['Sorted'])
        base_dir = config.get('base_dir', '.')
    else:
        categories = args.categories
        base_dir = args.base_dir

    base_dir = ensure_windows_path(base_dir)

    dest_folders = {cat: ensure_windows_path(os.path.join(base_dir, cat)) for cat in categories}
    delete_folder = ensure_windows_path(os.path.join(base_dir, 'deleted'))

    return {
        'source_folder': ensure_windows_path('.'),
        'categories': categories,
        'dest_folders': dest_folders,
        'delete_folder': delete_folder,
        'base_dir': base_dir
    }