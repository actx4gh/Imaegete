import argparse
import os
import platform
import subprocess

import yaml

APP_NAME = 'Imaegete'

RESIZE_TIMER_INTERVAL = 300
LOGGER_NAME = 'imaegete'
LOG_FILE_NAME = f'{LOGGER_NAME}.log'
WINDOW_TITLE_SUFFIX = 'Imaegete'

NEXT_KEY = 'Right'
PREV_KEY = 'Left'
FIRST_KEY = 'Home'
LAST_KEY = 'End'
RANDOM_KEY = 'R'
DELETE_KEY = 'Delete'
UNDO_KEY = 'U'
FULLSCREEN_KEY = 'F'

IMAGE_CACHE_MAX_SIZE_KB = 102400


class Config:
    """
    A class to handle the configuration setup for the application, including parsing command line arguments and reading YAML files.
    """

    def __init__(self):
        """
        Initialize the configuration by setting up platform-specific directories and loading the configuration.
        """
        self.platform_name = platform.system()
        self._default_config_dir = self._get_default_config_dir()
        self._config = self._initialize_configuration()

    def _is_cygwin(self):
        """
        Check if the current environment is Cygwin.

        :return: True if Cygwin is detected, False otherwise.
        :rtype: bool
        """
        ostype = os.getenv('OSTYPE', '').lower()
        return 'cygwin' in ostype

    def _cygwin_to_windows_path(self, cygwin_path):
        """
        Convert a Cygwin path to a Windows path.

        :param cygwin_path: The Cygwin file path to convert.
        :type cygwin_path: str
        :return: The converted Windows file path.
        :rtype: str
        """
        result = subprocess.run(['cygpath', '-w', cygwin_path], capture_output=True, text=True)
        return result.stdout.strip()

    def _ensure_windows_path(self, path):
        """
        Ensure the given path is in Windows format if running on Cygwin, otherwise return the absolute path.

        :param path: The file path to ensure.
        :type path: str
        :return: The ensured Windows or absolute file path.
        :rtype: str
        """
        if self._is_cygwin():
            return self._cygwin_to_windows_path(path)
        else:
            return os.path.abspath(path)

    def _parse_args(self, args=None):
        """
        Parse command line arguments for the configuration.

        :param args: Command line arguments to parse. If None, parse sys.argv.
        :type args: list or None
        :return: Parsed arguments as an argparse.Namespace object.
        :rtype: argparse.Namespace
        """
        parser = argparse.ArgumentParser(description=f"{APP_NAME} Configuration")
        parser.add_argument('--config', type=str, help="Path to the YAML configuration file")
        parser.add_argument('--categories', type=str, nargs='*', help="List of categories")
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
        """
        Get the default configuration directory based on the platform.

        :return: The default configuration directory.
        :rtype: str
        """
        system = self.platform_name

        if system == 'Darwin':
            config_dir = os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
        elif system == 'Linux' or 'CYGWIN' in system:
            config_dir = os.path.expanduser(f"~/.config/{APP_NAME}")
        elif system == 'Windows':
            config_dir = os.path.join(os.getenv('LOCALAPPDATA'), APP_NAME)
        else:
            raise RuntimeError(f"Unsupported OS: {system}")
        return config_dir

    def _read_config_file(self, config_path):
        """
        Read and load the YAML configuration file.

        :param config_path: The path to the YAML configuration file.
        :type config_path: str
        :return: The configuration as a dictionary.
        :rtype: dict
        """
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        return config

    def _initialize_configuration(self):
        """
        Initialize the application configuration by combining command line arguments and YAML file settings.
        :return: The initialized configuration as a dictionary.
        :rtype: dict
        """
        args = self._parse_args()

        config_dir = self._ensure_windows_path(args.config_dir)

        config = {
            'categories': args.categories,
            'log_level': args.log_level,
            'app_name': APP_NAME,
            'config_dir': config_dir,
            'log_dir': self._ensure_windows_path(args.log_dir) if args.log_dir else os.path.join(config_dir, 'logs'),
            'cache_dir': self._ensure_windows_path(args.cache_dir) if args.cache_dir else os.path.join(config_dir,
                                                                                                       'cache'),
            'sort_dir': self._ensure_windows_path(args.sort_dir) if args.sort_dir else None,
            'start_dirs': [self._ensure_windows_path(args.start_dirs)]
        }

        if args.config:
            file_config = self._read_config_file(args.config)

            config.update({k: v for k, v in file_config.items() if v is not None})

        if isinstance(config['start_dirs'], str):

            config['start_dirs'] = [self._ensure_windows_path(config['start_dirs'])]
        elif isinstance(config['start_dirs'], list):

            config['start_dirs'] = [self._ensure_windows_path(d.strip()) for d in config['start_dirs']]

        config['dest_folders'] = {}
        config['delete_folders'] = {}

        for start_dir in config['start_dirs']:
            sort_dir = config['sort_dir'] if config['sort_dir'] else start_dir

            if config.get('categories'):
                config['dest_folders'][start_dir] = {}

                for category in config['categories']:
                    category_path = self._ensure_windows_path(os.path.join(sort_dir, category))

                    config['dest_folders'][start_dir][category] = category_path

            delete_path = self._ensure_windows_path(os.path.join(sort_dir, 'deleted'))
            config['delete_folders'][start_dir] = delete_path

        return config

    def __getattr__(self, name):
        """
        Override the attribute getter to retrieve values from the configuration dictionary.

        :param name: The name of the attribute to retrieve.
        :type name: str
        :return: The value of the attribute from the configuration.
        :rtype: Any
        :raises AttributeError: If the attribute does not exist in the configuration.
        """
        if name in self._config:
            return self._config[name]
        raise AttributeError(f"'Config' object has no attribute '{name}'")


config_instance = Config()

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
platform_name = config_instance.platform_name
