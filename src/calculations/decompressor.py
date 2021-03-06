#!/usr/bin/env python3
# Copyright (c) 2022 FRC Team 1678: Citrus Circuits
"""Decompresses objective and subjective match collection QR codes."""

import enum
import os

import yaml

import utils
from calculations import base_calculations
from calculations import qr_state
from calculations.qr_state import QRState


class QRType(enum.Enum):
    """Enum that stores QR types."""

    OBJECTIVE = 0
    SUBJECTIVE = 1


class Decompressor(base_calculations.BaseCalculations):

    # Load latest match collection compression QR code schema
    SCHEMA = qr_state.SCHEMA
    _GENERIC_DATA_FIELDS = QRState._get_data_fields("generic_data")
    OBJECTIVE_QR_FIELDS = _GENERIC_DATA_FIELDS.union(QRState._get_data_fields("objective_tim"))
    SUBJECTIVE_QR_FIELDS = _GENERIC_DATA_FIELDS.union(QRState._get_data_fields("subjective_aim"))
    TIMELINE_FIELDS = QRState.get_timeline_info()

    MISSING_TIM_IGNORE_FILE_PATH = utils.create_file_path("data/missing_tim_ignore.yml")

    def __init__(self, server):
        super().__init__(server)
        self.watched_collections = ["raw_qr"]

    def convert_data_type(self, value, type_, name=None):
        """Convert from QR string representation to database data type."""
        # Enums are stored as int in the database
        if type_ == "int":
            return int(value)
        if type_ == "float":
            return float(value)
        if type_ == "bool":
            return utils.get_bool(value)
        if type_ == "str":
            return value  # Value is already a str
        if type_ == "Enum":
            return self.get_decompressed_name(value, name)
        raise ValueError(f"Type {type_} not recognized")

    def get_decompressed_name(self, compressed_name, section):
        """Returns decompressed variable name from schema.

        compressed_name: str - Compressed variable name within QR code
        section: str - Section of schema that name comes from.
        """
        for key, value in self.SCHEMA[section].items():
            if isinstance(value, list):
                if value[0] == compressed_name:
                    return key
            else:
                if value == compressed_name:
                    return key
        raise ValueError(f"Retrieving Variable Name {compressed_name} from {section} failed.")

    def get_decompressed_type(self, name, section):
        """Returns server-side data type from schema.

        name: str - Decompressed variable name within Schema
        section: str - Section of schema that name comes from.
        """
        # Type all items after the first item
        type_ = self.SCHEMA[section][name][1:]
        # Detect special case of data type being a list
        if len(type_) > 1:
            return type_  # Returns list of the type (list) and the type of data stored in the list
        return type_[0]  # Return the type of the value

    def decompress_data(self, data, section):
        """Decompress (split) data given the section of the QR it came from.

        This matches compressed data names to actual variable names. It treats embedded dictionaries as
        special cases, a parsing function needs to be written for each (e.g. timeline).
        """
        decompressed_data = {}
        # Iterate through data
        for data_field in data:
            compressed_name = data_field[0]  # Compressed name is always first character
            value = data_field[1:]  # Actual data value is everything after the first character
            # Get uncompressed name and the target data type
            uncompressed_name = self.get_decompressed_name(compressed_name, section)
            uncompressed_type = self.get_decompressed_type(uncompressed_name, section)
            # Detect special cases in typing (e.g. value is list)
            if isinstance(uncompressed_type, list):
                # If second data type is dictionary, it should be handled separately
                if "dict" in uncompressed_type:
                    # Decompress timeline
                    if uncompressed_name == "timeline":
                        typed_value = self.decompress_timeline(value)
                    # Value is not one of the currently known dictionaries
                    else:
                        raise NotImplementedError(
                            f"Decompression of {uncompressed_name} as a dict not supported."
                        )
            else:  # Normal data type
                typed_value = self.convert_data_type(value, uncompressed_type, uncompressed_name)
            decompressed_data[uncompressed_name] = typed_value
        return decompressed_data

    def decompress_generic_qr(self, data):
        """Decompress generic section of QR or raise error if schema is outdated."""
        # Split data by separator specified in schema
        data = data.split(self.SCHEMA["generic_data"]["_separator"])
        for entry in data:
            if entry[0] == "A":
                schema_version = int(entry[1:])
                if schema_version != self.SCHEMA["schema_file"]["version"]:
                    raise LookupError(
                        f'QR Schema (v{schema_version}) does not match Server version (v{self.SCHEMA["schema_file"]["version"]})'
                    )
        return self.decompress_data(data, "generic_data")

    def decompress_timeline(self, data):
        """Decompress the timeline based on schema."""
        decompressed_timeline = []  # Timeline is a list of dictionaries
        # Return empty list if timeline is empty
        if data == "":
            return decompressed_timeline
        timeline_length = sum([entry["length"] for entry in self.TIMELINE_FIELDS])
        if len(data) % timeline_length != 0:
            raise ValueError(f"Invalid timeline -- Timeline length invalid: {data}")
        # Split into list of actions. Each action is a string of length timeline_length
        timeline_actions = [
            data[i : i + timeline_length] for i in range(0, len(data), timeline_length)
        ]
        for action in timeline_actions:
            decompressed_action = dict()
            current_position = 0
            for entry in self.TIMELINE_FIELDS:
                # Get untyped value by slicing action string from current position to next position
                next_position = current_position + entry["length"]
                untyped_value = action[current_position:next_position]
                # Set action value to the converted data type
                decompressed_action[entry["name"]] = self.convert_data_type(
                    untyped_value, entry["type"], entry["name"]
                )
                current_position = next_position
            decompressed_timeline.append(decompressed_action)
        return decompressed_timeline

    def get_qr_type(self, first_char):
        """Returns the qr type from QRType enum based on first character."""
        if first_char == self.SCHEMA["objective_tim"]["_start_character"]:
            return QRType.OBJECTIVE
        if first_char == self.SCHEMA["subjective_aim"]["_start_character"]:
            return QRType.SUBJECTIVE
        raise ValueError(f"QR type unknown - Invalid first character for QR: {first_char}")

    def decompress_single_qr(self, qr_data, qr_type):
        """Decompress a full QR."""
        # Split into generic data and objective/subjective data
        qr_data = qr_data.split(self.SCHEMA["generic_data"]["_section_separator"])
        # Generic QR is first section of QR
        decompressed_data = []
        # Decompress subjective QR
        if qr_type == QRType.SUBJECTIVE:
            teams_data = qr_data[1].split(self.SCHEMA["subjective_aim"]["_team_separator"])
            if len(teams_data) != 3:
                raise IndexError("Incorrect number of teams in Subjective QR")
            for team in teams_data:
                decompressed_document = self.decompress_generic_qr(qr_data[0])
                subjective_data = team.split(self.SCHEMA["subjective_aim"]["_separator"])
                decompressed_document.update(
                    self.decompress_data(subjective_data, "subjective_aim")
                )
                decompressed_data.append(decompressed_document)
                if set(decompressed_document.keys()) != self.SUBJECTIVE_QR_FIELDS:
                    raise ValueError("QR missing data fields")
        elif qr_type == QRType.OBJECTIVE:  # Decompress objective QR
            objective_data = qr_data[1].split(self.SCHEMA["objective_tim"]["_separator"])
            decompressed_document = self.decompress_generic_qr(qr_data[0])
            decompressed_document.update(self.decompress_data(objective_data, "objective_tim"))
            decompressed_data.append(decompressed_document)
            if set(decompressed_document.keys()) != self.OBJECTIVE_QR_FIELDS:
                raise ValueError("QR missing data fields")
            utils.log_info(
                f'Match: {decompressed_document["match_number"]} '
                f'Team: {decompressed_document["team_number"]} '
                f'Scout_ID: {decompressed_document["scout_id"]}'
            )
        return decompressed_data

    def decompress_qrs(self, split_qrs):
        """Decompresses a list of QRs. Returns dict of decompressed QRs split by type."""
        output = {"unconsolidated_obj_tim": [], "subj_tim": []}
        utils.log_info(f"Started decompression on qr batch")
        for qr in split_qrs:
            qr_type = utils.catch_function_errors(self.get_qr_type, qr["data"][0])
            if qr_type is None:
                continue
            # Remove identification character
            qr = qr["data"][1:]
            decompressed_qr = utils.catch_function_errors(self.decompress_single_qr, qr, qr_type)
            if decompressed_qr is None:
                continue
            if qr_type == QRType.OBJECTIVE:
                output["unconsolidated_obj_tim"].extend(decompressed_qr)
            elif qr_type == QRType.SUBJECTIVE:
                output["subj_tim"].extend(decompressed_qr)
        utils.log_info(f"Finished decompression on qr batch")
        return output

    def check_scout_ids(self):
        """Checks unconsolidated TIMs in `tim_queue` to see which scouts have not sent data.

        This operation is done by `scout_id` -- if a match is missing data, then the scout_id will not
        have sent data for the match.
        returns None -- warnings are issued directly through `utils.log_warning`.
        """
        # Load matches or matches and ids to ignore from ignore file
        if os.path.exists(self.MISSING_TIM_IGNORE_FILE_PATH):
            with open(self.MISSING_TIM_IGNORE_FILE_PATH) as ignore_file:
                items_to_ignore = yaml.load(ignore_file, Loader=yaml.Loader)
        else:
            items_to_ignore = []
        matches_to_ignore = [item["match_number"] for item in items_to_ignore if len(item) == 1]
        tims = self.server.db.find("unconsolidated_obj_tim")
        matches = {}
        for tim in tims:
            match_number = tim["match_number"]
            matches[match_number] = matches.get(match_number, []) + [tim["scout_id"]]

        for match, scout_ids in matches.items():
            if match in matches_to_ignore:
                continue
            unique_scout_ids = []
            for id_ in scout_ids:
                if id_ in unique_scout_ids:
                    if {"match_number": match, "scout_id": id_} not in items_to_ignore:
                        utils.log_warning(f"Duplicate Scout ID {id_} for Match {match}")
                else:
                    unique_scout_ids.append(id_)
            # Scout IDs are from 1-18 inclusive
            for id_ in range(1, 19):
                if id_ not in unique_scout_ids:
                    if {"match_number": match, "scout_id": id_} not in items_to_ignore:
                        utils.log_warning(f"Scout ID {id_} missing from Match {match}")

    def run(self):
        new_qrs = [
            entry["o"] for entry in self.entries_since_last() if not entry["o"]["blocklisted"]
        ]
        decompressed_qrs = self.decompress_qrs(new_qrs)
        for collection in ["unconsolidated_obj_tim", "subj_tim"]:
            if self.calc_all_data:
                # Prevent duplicates when calculating all data by deleting data before inserting
                # Updating doesn't work because unconsolidated_obj_tim doesn't have unique keys
                self.server.db.delete_data(collection)
            self.server.db.insert_documents(collection, decompressed_qrs[collection])
