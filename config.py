import os
import subprocess
import argparse
import yaml

class Config:
    def __init__(self):
        self._config = self._initialize_configuration()

    def _is_cygwin(self):
        ostype = os.getenv('OSTYPE', '').lower()
        return 'cygwin' in ostype

    def _cygwin_to_windows_path(self, cygwin_path):
        result = subprocess.run(['cygpath', '-w', cygwin_path], capture_output=True, text=True)
        return result.stdout.strip()

    def _ensure_windows_path(self, path):
        if self._is_cygwin():
            return self._cygwin_to_windows_path(path)
        else:
            return os.path.abspath(path)

    def _parse_args(self, args=None):
        parser = argparse.ArgumentParser(description="Image Sorter Configuration")
        parser.add_argument('--config', type=str, help="Path to the YAML configuration file")
        parser.add_argument('--categories', type=str, nargs='*', default=['Sorted'], help="List of categories")
        parser.add_argument('--base_dir', type=str, default='.', help="Base directory for category folders")
        return parser.parse_args(args)

    def _read_config_file(self, config_path):
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        return config

    def _initialize_configuration(self):
        args = self._parse_args()

        if args.config:
            config = self._read_config_file(args.config)
            categories = config.get('categories', ['Sorted'])
            base_dir = config.get('base_dir', '.')
        else:
            categories = args.categories
            base_dir = args.base_dir

        base_dir = self._ensure_windows_path(base_dir)

        dest_folders = {cat: self._ensure_windows_path(os.path.join(base_dir, cat)) for cat in categories}
        delete_folder = self._ensure_windows_path(os.path.join(base_dir, 'deleted'))

        return {
            'source_folder': self._ensure_windows_path('.'),
            'categories': categories,
            'dest_folders': dest_folders,
            'delete_folder': delete_folder,
            'base_dir': base_dir
        }

    def __getattr__(self, name):
        if name in self._config:
            return self._config[name]
        raise AttributeError(f"'Config' object has no attribute '{name}'")


# Singleton instance of the configuration
config_instance = Config()

# Expose attributes at the module level
categories = config_instance.categories
dest_folders = config_instance.dest_folders
delete_folder = config_instance.delete_folder
base_dir = config_instance.base_dir
source_folder = config_instance.source_folder
