import logging

def setup_logging():
    logging.basicConfig(filename='image_sorter.log', level=logging.INFO, format='%(asctime)s - %(message)s')

