import argparse
import os
import platform
import subprocess

import yaml

APP_NAME = 'ImageSorter'


class Config:
    def __init__(self):
        self._default_config_dir = self._get_default_config_dir()
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
        parser.add_argument('--sort_dir', type=str, default='.',
                            help="Base directory for sorting folders. Defaults to CWD")
        parser.add_argument('--log_dir', type=str, help="Where to store logs. Defaults to CONFIG_DIR/logs")
        parser.add_argument('--cache_dir', type=str, help="Where to cache data. Defaults to CONFIG_DIR/cache")
        parser.add_argument('--config_dir', type=str, default=self._default_config_dir,
                            help=f"Where to load/save config data. Defaults to {self._default_config_dir}")
        parser.add_argument('--log_level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                            default='INFO', help="Logging level")
        return parser.parse_args(args)

    def _get_default_config_dir(self):
        system = platform.system()

        if system == 'Darwin':  # macOS
            config_dir = os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
        elif system == 'Linux' or 'CYGWIN' in system:  # Linux and Cygwin
            config_dir = os.path.expanduser(f"~/.config/{APP_NAME}")
        elif system == 'Windows':  # Windows
            config_dir = os.path.join(os.getenv('LOCALAPPDATA'), APP_NAME)
        else:
            raise RuntimeError(f"Unsupported OS: {system}")
        return config_dir

    def _read_config_file(self, config_path):
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        return config

    def _initialize_configuration(self):
        args = self._parse_args()

        # Resolve the config directory first
        config_dir = self._ensure_windows_path(args.config_dir)

        # Set default log and cache directories using the resolved config_dir
        default_log_dir = os.path.join(config_dir, 'logs')
        default_cache_dir = os.path.join(config_dir, 'cache')

        # Initialize with default values
        config = {
            'categories': args.categories,
            'sort_dir': self._ensure_windows_path(args.sort_dir),
            'log_level': args.log_level,
            'app_name': APP_NAME,
            'config_dir': config_dir,
            'log_dir': self._ensure_windows_path(args.log_dir) if args.log_dir else default_log_dir,
            'cache_dir': self._ensure_windows_path(args.cache_dir) if args.cache_dir else default_cache_dir,
            'source_folder': os.path.abspath('.')
        }

        if args.config:
            file_config = self._read_config_file(args.config)
            # Update config with values from the file if they are not None
            config.update({k: v for k, v in file_config.items() if v is not None})

        config['dest_folders'] = {cat: self._ensure_windows_path(os.path.join(config['sort_dir'], cat)) for cat in
                                  config['categories']}
        config['delete_folder'] = self._ensure_windows_path(os.path.join(config['sort_dir'], 'deleted'))

        return config

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
sort_dir = config_instance.sort_dir
source_folder = config_instance.source_folder
log_level = config_instance.log_level
app_name = config_instance.app_name
log_dir = config_instance.log_dir
cache_dir = config_instance.cache_dir
config_dir = config_instance.config_dir
