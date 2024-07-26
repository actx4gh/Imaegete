import os
import subprocess
import argparse
import yaml

def cygwin_to_windows_path(cygwin_path):
    result = subprocess.run(['cygpath', '-w', cygwin_path], capture_output=True, text=True)
    return result.stdout.strip()

def parse_args():
    parser = argparse.ArgumentParser(description="Image Sorter Configuration")
    parser.add_argument('--config', type=str, help="Path to the YAML configuration file")
    parser.add_argument('--categories', type=str, nargs='*', default=['Sorted'], help="List of categories")
    parser.add_argument('--base_dir', type=str, default='.', help="Base directory for category folders")
    return parser.parse_args()

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

    base_dir = os.path.abspath(base_dir)

    dest_folders = {cat: cygwin_to_windows_path(os.path.join(base_dir, cat)) for cat in categories}
    delete_folder = cygwin_to_windows_path(os.path.join(base_dir, 'deleted'))

    return {
        'source_folder': '.',
        'categories': categories,
        'dest_folders': dest_folders,
        'delete_folder': delete_folder,
        'base_dir': base_dir
    }

def ensure_directories_exist(dest_folders, delete_folder):
    for folder in dest_folders.values():
        os.makedirs(folder, exist_ok=True)
    os.makedirs(delete_folder, exist_ok=True)

