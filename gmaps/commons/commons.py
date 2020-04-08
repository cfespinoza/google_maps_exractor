import json
import logging
import os
import sys


def init_default_handler(level=None, root_dir=None, name=None, date=None):
    date_str = date.strftime("%d_%m_%Y_%H_%M_%S")
    log_file_name = "{name}-{date_str}.log".format(name=name, date_str=date_str)
    log_dir = root_dir if root_dir else os.getcwd()
    log_file_path = os.path.join(log_dir, log_file_name)
    logging.basicConfig(
        level=logging.getLevelName(level),
        datefmt="%d-%m-%Y %H:%M:%S",
        format="[%(asctime)s] [%(levelname)8s] --- %(message)s (%(filename)s:%(lineno)d)",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file_path)
        ]
    )


def get_obj_from_file(file_path=None):
    with open(file_path, 'r') as f:
        config_obj = json.load(f)
    return config_obj


def validate_required_keys(keys=None, obj=None):
    all_present = [k in obj.keys() for k in keys]
    return all(all_present)


def get_zip_codes_obj_config(input_config=None, reader=None):
    if input_config.get("type") == "local":
        return input_config.get("local")
    elif input_config.get("type") == "file":
        config = input_config.get("file")
        config.update({"zip_codes": get_obj_from_file(config.get("file_path"))})
        return config
    elif input_config.get("type") == "db":
        if reader:
            return reader.read()
        else:
            return None
    else:
        return None
