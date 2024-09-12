import os
import pytest

def test_get_image_list(image_handler):
    handler = image_handler
    test_image_path = os.path.join(handler.source_folder, 'test.jpg')
    with open(test_image_path, 'w') as f:
        f.write("test image")
    assert handler.get_image_list() == ['test.jpg']

def test_load_image(image_handler, test_jpg):
    handler = image_handler
    test_image_path = os.path.join(handler.source_folder, 'test.jpg')
    test_jpg(test_image_path)
    handler.image_list = handler.get_image_list()
    image = handler.load_image(0)
    assert image is not None
    image.close()  

def test_move_file(image_handler):
    handler = image_handler
    src = os.path.join(handler.source_folder, 'test.jpg')
    dest = os.path.join(handler.dest_folders['cat1'], 'test.jpg')
    with open(src, 'w') as f:
        f.write("test image")
    handler.move_file(src, dest)
    assert os.path.isfile(dest)

def test_delete_image(image_handler):
    handler = image_handler
    with open(os.path.join(handler.source_folder, 'test.jpg'), 'w') as f:
        f.write("test image")
    handler.image_list = handler.get_image_list()
    handler.delete_image()
    assert not handler.image_list

def test_undo_last_action(image_handler):
    handler = image_handler
    with open(os.path.join(handler.source_folder, 'test.jpg'), 'w') as f:
        f.write("test image")
    handler.image_list = handler.get_image_list()
    handler.delete_image()
    handler.undo_last_action()
    assert handler.image_list
