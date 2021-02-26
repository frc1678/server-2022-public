#! /usr/bin/env python3
# Copyright (c) 2019-2021 FRC Team 1678: Citrus Circuits
"""Contains the server class."""
import importlib
from typing import List

import yaml

from calculations.base_calculations import BaseCalculations
from data_transfer import database, cloud_db_updater
import utils


class Server:
    """Contains the logic that runs calculations in proper order.

    Calculation classes should contain a `run` method that accepts one argument, an instance of this
    class. They should use the `db` attribute of this server class to communicate with the local
    database.
    """

    CALCULATIONS_FILE = utils.create_file_path('src/calculations.yml')

    def __init__(self):
        self.db = database.Database()
        self.oplog = self.db.client.local.oplog.rs
        self.cloud_db_updater = cloud_db_updater.CloudDBUpdater()

        self.calculations: List[BaseCalculations] = self.load_calculations()

    def load_calculations(self):
        """Imports calculation modules and creates instances of calculation classes."""
        with open(self.CALCULATIONS_FILE) as f:
            calculation_load_list = yaml.load(f, Loader=yaml.Loader)
        loaded_calcs = []
        # `calculations.yml` is a list of dictionaries, each with an "import_path" and "class_name"
        # key. We need to import the module and then get the class from the imported module.
        for calc in calculation_load_list:
            # Import the module
            module = importlib.import_module(calc["import_path"])
            # Get calculation class from module
            cls = getattr(module, calc["class_name"])
            # Append an instance of calculation class to the calculations list
            # We pass `self` as the only argument to the `__init__` method of the calculation class
            # so the calculations can get access to server instance variables such as the oplog
            # or the database
            loaded_calcs.append(cls(self))
        return loaded_calcs

    def run_calculations(self):
        """Run each calculation in `self.calculations` in order"""
        for calc in self.calculations:
            calc.run()

    def run(self):
        """Starts server cycles, runs in infinite loop"""
        write_cloud_question = input('Write changes to cloud db? y/N').lower()
        if write_cloud_question in ['y', 'yes']:
            write_cloud = True
        else:
            write_cloud = False
        while True:
            self.run_calculations()
            if write_cloud:
                self.cloud_db_updater.write_db_changes()


if __name__ == '__main__':
    server = Server()
    server.run()
