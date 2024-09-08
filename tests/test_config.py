import os
import tempfile
import yaml
from core.config import is_cygwin, parse_args, read_config_file, get_configuration, ensure_directories_exist


def test_is_cygwin():
    # Test cygwin
    os.environ['OSTYPE'] = 'cygwin'
    result = is_cygwin()
    assert result == True

    # Test linux
    os.environ['OSTYPE'] = 'linux'
    result = is_cygwin()
    assert result == False


def test_parse_args(monkeypatch):
    test_args = ['--config', 'config.yaml', '--categories', 'cat1', 'cat2', '--base_dir', '/tmp']
    args = parse_args(test_args)
    assert args.config == 'config.yaml'
    assert args.categories == ['cat1', 'cat2']
    assert args.base_dir == '/tmp'

def test_read_config_file():
    config_data = {
        'categories': ['Category1', 'Category2'],
        'base_dir': '/tmp'
    }
    with tempfile.NamedTemporaryFile('w', delete=False) as temp:
        yaml.dump(config_data, temp)
        temp_path = temp.name

    config = read_config_file(temp_path)
    assert config['categories'] == ['Category1', 'Category2']
    assert config['base_dir'] == '/tmp'

def test_get_configuration(monkeypatch):
    def mock_parse_args(args=None):
        return type('Args', (object,), {'config': None, 'categories': ['TestCat'], 'base_dir': '.'})
    monkeypatch.setattr('config.parse_args', mock_parse_args)
    config = get_configuration()
    assert config['categories'] == ['TestCat']
    assert 'TestCat' in config['dest_folders']

def test_ensure_directories_exist():
    with tempfile.TemporaryDirectory() as temp_dir:
        dest_folders = {'Cat1': os.path.join(temp_dir, 'Cat1')}
        delete_folder = os.path.join(temp_dir, 'deleted')
        ensure_directories_exist(dest_folders, delete_folder)
        assert os.path.isdir(dest_folders['Cat1'])
        assert os.path.isdir(delete_folder)
