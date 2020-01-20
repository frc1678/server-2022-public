#!/usr/bin/python3.6
# Copyright (c) 2019 FRC Team 1678: Citrus Circuits
"""Holds functions for database communication

All communication with the MongoDB local database go through this file
"""
# External imports
from pymongo import MongoClient
# Internal imports
import utils

DB = MongoClient('localhost', 27017).scouting_system


def overwrite_data_points(data, path, overwrite, competition='current'):
    """Updates data in an embedded array by overwriting previous data

    data is a string containing data to add to the collection
    path is a string joined by '.' communicating where within the collection the data is added
    overwrite is a string communicating what to overwrite within the array
    competition is the competition code
    """
    if competition == 'current':
        competition = utils.TBA_EVENT_KEY
    # Adds data to the correct path within the competition document
    DB.competitions.update_one({"tba_event_key": competition, path: overwrite},
                               {"$set": {path + '.$': data}})


def overwrite_document(data, path, competition='current'):
    """Updates data in an embedded document by overwriting previous data

    data is a list containing data to add to the collection
    path is a string joined by '.' communicating where within the collection the data is added
    competition is the competition code
    """
    if competition == 'current':
        # Obtains the event_code from competition.txt, the file created in setup_competition
        competition = utils.TBA_EVENT_KEY
    # Adds data to the correct path within the competition document
    DB.competitions.update_one({"tba_event_key": competition}, {"$set": {path: data}})


def append_document(data, path, competition='current'):
    """Appends the database with new data

    data is a list containing data to add to the collection
    path is a string joined by '.' communicating where within the collection the data is added
    competition is the competition code
    """
    if competition == 'current':
        # Obtains the event_code from competition.txt, the file created in setup_competition
        competition = utils.TBA_EVENT_KEY
    # Adds data to the correct path within the competition document
    DB.competitions.update_one({"tba_event_key": competition}, {'$push': {path: {'$each': data}}})


def select_from_database(query, projection):
    """Selects data from the 'competitions' collection

    query is a dictionary containing the selection filter
    projection is a dictionary containing the data field to collect
    """
    result = []
    cursor = DB.competitions.find(query, projection)
    for i in cursor:
        result.append(i)
    return result


def select_one_from_database(query, projection=None):
    """Selects a single data set from the 'competitions' collection

    query is a dictionary containing the selection filter
    projection is a dictionary containing the data field to collect
    """
    # Infers projection from query if projection is not specified
    if projection is None:
        query_keys = query.keys()
        for i in query_keys:
            if i == 'raw':
                projection = {'raw': 1}
                break
            if i == 'tba_cache':
                projection = {'tba_cache': 1}
                break
            if i == 'processed':
                projection = {'processed': 1}
                break
    # Finds the query within the database
    result = DB.competitions.find_one(query, projection)
    # Simplifies the result
    new_result = result
    if result is not None:
        # Removes the id
        result.pop('_id')
        keys = list(result.keys())
        # Removes unnecessary path information to simplify the result of the function and make it
        # easier to use
        for i in keys:
            if i == 'raw':
                new_result = result.get('raw')
                break
            elif i == 'tba_cache':
                new_result = result.get('tba_cache')
                break
            elif i == 'processed':
                new_result = result.get('processed')
                break
    return new_result


def select_from_within_array(path, filter):
    """Selects data from an embedded document within an array

    path is a string joined by '.' communicating where within the collection the data is located
    filter is a list containing a key and value pair that exists within the document"""
    result = DB.competitions.aggregate([
       {
          '$project': {
             path: {
                '$filter': {
                   'input': f'${path}',
                   'as': 'item',
                   'cond': {'$eq': ['$$item.' + filter[0], filter[1]]}
                }
             }
          }
       }
    ])
    new_result = []
    for i in result:
        new_result.append(i)
    return new_result

def add_competition(tba_event_key):
    """Adds a new document for the competition into the 'competitions' collection"""
    # Extracts the year from the 'tba_event_key'
    year = int(tba_event_key[0:4])
    DB.competitions.insert_one({
        'year': year,
        'tba_event_key': tba_event_key,
        'raw': {
            'qr': [],
            'pit': [],
        },
        'tba_cache': [],
        'processed': {
            'replay_outdated_qr': [],
            'unconsolidated_obj_tim': [],
            'consolidated_obj_tim': [],
            'subj_aim': [],
            'calc_team': [],
            'calc_match': [],
            'calc_obj_tim': [],
        },
    })
