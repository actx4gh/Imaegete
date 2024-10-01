import os

from confumo.confumo import Confumo

APP_NAME = 'Imaegete'

# Constants
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
QUIT_KEY = 'Q'

IMAGE_CACHE_MAX_SIZE_KB = 102400


class Config(Confumo):
    """
    Subclass of BaseConfiguration to handle specific application configurations,
    extending the base argument parsing with additional options.
    """

    def __init__(self, app_name=APP_NAME, additional_args=None):
        # Define additional arguments specific to this application
        additional_args = [
            {'flags': ['--categories'], 'kwargs': {'type': str, 'nargs': '*', 'help': "List of categories"}},
            {'flags': ['--sort_dir'],
             'kwargs': {'type': str, 'help': "Base directory to put sorting folders. Defaults to START_DIR"}},
            {'flags': ['--start_dirs'],
             'kwargs': {'type': str, 'default': '.', 'help': "Base image dirs. Defaults to CWD"}},
            {'flags': ['--log_dir'],
             'kwargs': {'type': str, 'help': "Where to store logs. Defaults to CONFIG_DIR/logs"}},
            {'flags': ['--cache_dir'],
             'kwargs': {'type': str, 'help': "Where to cache data. Defaults to CONFIG_DIR/cache"}},
        ]
        # Call the base class's __init__ method with app_name and additional_args
        super().__init__(app_name=app_name, additional_args=additional_args)
        self._setup_module_attributes()
        self._initialize_configuration()

    def _initialize_configuration(self):
        """
        Initialize the application configuration by combining command line arguments and YAML file settings.
        This extends the base configuration initialization by adding app-specific logic.
        """
        args = self.args

        config_dir = self._ensure_windows_path(args.config_dir)

        config = {
            'categories': args.categories,
            'log_dir': self._ensure_windows_path(args.log_dir) if args.log_dir else os.path.join(config_dir, 'logs'),
            'cache_dir': self._ensure_windows_path(args.cache_dir) if args.cache_dir else os.path.join(config_dir,
                                                                                                       'cache'),
            'sort_dir': self._ensure_windows_path(args.sort_dir) if args.sort_dir else None,
            'start_dirs': [self._ensure_windows_path(args.start_dirs)]
        }

        # Read the YAML config file if provided
        if args.config:
            file_config = self._read_config_file(args.config)
            config.update({k: v for k, v in file_config.items() if v is not None})

        # Ensure 'start_dirs' is always a list of absolute paths
        if isinstance(config['start_dirs'], str):
            config['start_dirs'] = [self._ensure_windows_path(config['start_dirs'])]
        elif isinstance(config['start_dirs'], list):
            config['start_dirs'] = [self._ensure_windows_path(d.strip()) for d in config['start_dirs']]

        # Add default folders for sorted files and deleted files
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

config = Config.get_instance()