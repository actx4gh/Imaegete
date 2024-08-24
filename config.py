import argparse
import os
import platform
import subprocess

import yaml

APP_NAME = 'ImageSorter'


class Config:
    def __init__(self):
        self.platform_name = platform.system()  # Added platform_name attribute
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
        parser.add_argument('--sort_dir', type=str, help="Base directory to put sorting folders. Defaults to START_DIR")
        parser.add_argument('--start_dirs', type=str, default='.', help="Base image dirs. Defaults to CWD")
        parser.add_argument('--log_dir', type=str, help="Where to store logs. Defaults to CONFIG_DIR/logs")
        parser.add_argument('--cache_dir', type=str, help="Where to cache data. Defaults to CONFIG_DIR/cache")
        parser.add_argument('--config_dir', type=str, default=self._default_config_dir,
                            help=f"Where to load/save config data. Defaults to {self._default_config_dir}")
        parser.add_argument('--log_level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                            default='INFO', help="Logging level")
        return parser.parse_args(args)

    def _get_default_config_dir(self):
        system = self.platform_name  # Use the platform_name attribute

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
        # Start with defaults from the command-line arguments
        config = {
            'categories': args.categories,
            'log_level': args.log_level,
            'app_name': APP_NAME,
            'config_dir': config_dir,
            'log_dir': self._ensure_windows_path(args.log_dir) if args.log_dir else os.path.join(config_dir, 'logs'),
            'cache_dir': self._ensure_windows_path(args.cache_dir) if args.cache_dir else os.path.join(config_dir,
                                                                                                       'cache'),
            'sort_dir': self._ensure_windows_path(args.sort_dir) if args.sort_dir else None,
            'start_dirs': [self._ensure_windows_path(args.start_dirs)]  # Set default start_dirs from args
        }

        # Load configuration from the YAML file if provided
        if args.config:
            file_config = self._read_config_file(args.config)
            # Update config with values from the file if they are not None
            config.update({k: v for k, v in file_config.items() if v is not None})

        # Convert start_dirs to a list of paths
        if isinstance(config['start_dirs'], str):
            # Convert single start_dir string into a list
            config['start_dirs'] = [self._ensure_windows_path(config['start_dirs'])]
        elif isinstance(config['start_dirs'], list):
            # Convert each start_dir in the list
            config['start_dirs'] = [self._ensure_windows_path(d.strip()) for d in config['start_dirs']]

        config['dest_folders'] = {}
        config['delete_folders'] = {}

        for start_dir in config['start_dirs']:
            sort_dir = config['sort_dir'] if config['sort_dir'] else start_dir

            # Initialize nested dictionaries for each start_dir
            config['dest_folders'][start_dir] = {}

            for category in config['categories']:
                category_path = self._ensure_windows_path(os.path.join(sort_dir, category))

                # Correctly map category to path specific to each start_dir
                config['dest_folders'][start_dir][category] = category_path

            delete_path = self._ensure_windows_path(os.path.join(sort_dir, 'deleted'))
            config['delete_folders'][start_dir] = delete_path

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
delete_folders = config_instance.delete_folders
sort_dir = config_instance.sort_dir
log_level = config_instance.log_level
app_name = config_instance.app_name
log_dir = config_instance.log_dir
cache_dir = config_instance.cache_dir
config_dir = config_instance.config_dir
start_dirs = config_instance.start_dirs
platform_name = config_instance.platform_name  # Expose platform_name at module level
