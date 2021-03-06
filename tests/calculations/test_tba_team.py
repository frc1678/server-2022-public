#!/usr/bin/env python3
# Copyright (c) 2022 FRC Team 1678: Citrus Circuits
"""This file tests the functions provided in tba_team that
don't require the database.
"""

from cmath import exp
from calculations import tba_team
from data_transfer import database
import utils
from server import Server

import pytest
from unittest.mock import patch


@pytest.mark.clouddb
class TestTBATeamCalc:
    def setup_method(self, method):
        with patch("server.Server.ask_calc_all_data", return_value=False):
            self.test_server = Server()
        self.test_calc = tba_team.TBATeamCalc(self.test_server)

    def test___init__(self):
        """Test if attributes are set correctly"""
        assert self.test_calc.watched_collections == ["obj_tim", "tba_tim"]
        assert self.test_calc.server == self.test_server

    def test_run(self):
        teams = {
            "api_url": f"event/{Server.TBA_EVENT_KEY}/teams/simple",
            "data": [
                {
                    "city": "Atascadero",
                    "country": "USA",
                    "key": "frc973",
                    "nickname": "Greybots",
                    "state_prov": "California",
                    "team_number": 973,
                },
                {
                    "city": "Davis",
                    "country": "USA",
                    "key": "frc1678",
                    "nickname": "Citrus Circuits",
                    "state_prov": "California",
                    "team_number": 1678,
                },
            ],
        }
        obj_tims = [
            {
                "auto_low_balls": 66,
                "auto_high_balls": 61,
                "tele_low_balls": 18,
                "tele_high_balls": 45,
                "incap": 14,
                "confidence_rating": 30,
                "team_number": 973,
                "match_number": 1,
            },
            {
                "auto_low_balls": 30,
                "auto_high_balls": 59,
                "tele_low_balls": 57,
                "tele_high_balls": 1,
                "incap": 22,
                "confidence_rating": 68,
                "team_number": 973,
                "match_number": 2,
            },
            {
                "auto_low_balls": 84,
                "auto_high_balls": 92,
                "tele_low_balls": 40,
                "tele_high_balls": 67,
                "incap": 18,
                "confidence_rating": 2,
                "team_number": 973,
                "match_number": 3,
            },
            {
                "auto_low_balls": 47,
                "auto_high_balls": 76,
                "tele_low_balls": 34,
                "tele_high_balls": 81,
                "incap": 17,
                "confidence_rating": 31,
                "team_number": 1678,
                "match_number": 1,
            },
            {
                "auto_low_balls": 25,
                "auto_high_balls": 54,
                "tele_low_balls": 81,
                "tele_high_balls": 59,
                "incap": 93,
                "confidence_rating": 14,
                "team_number": 1678,
                "match_number": 2,
            },
            {
                "auto_low_balls": 54,
                "auto_high_balls": 49,
                "tele_low_balls": 88,
                "tele_high_balls": 74,
                "incap": 15,
                "confidence_rating": 77,
                "team_number": 1678,
                "match_number": 3,
            },
        ]
        tba_tims = [
            {
                "auto_line": False,
                "match_number": 1,
                "team_number": 973,
            },
            {
                "auto_line": False,
                "match_number": 2,
                "team_number": 973,
            },
            {
                "auto_line": True,
                "match_number": 3,
                "team_number": 973,
            },
            {
                "auto_line": True,
                "match_number": 1,
                "team_number": 1678,
            },
            {
                "auto_line": False,
                "match_number": 2,
                "team_number": 1678,
            },
            {
                "auto_line": True,
                "match_number": 3,
                "team_number": 1678,
            },
        ]
        expected_results = [
            {
                "team_number": 973,
                "auto_line_successes": 1,
                "team_name": "Greybots",
            },
            {
                "team_number": 1678,
                "auto_line_successes": 2,
                "team_name": "Citrus Circuits",
            },
        ]
        self.test_server.db.insert_documents("tba_cache", teams)
        self.test_server.db.insert_documents("obj_tim", obj_tims)
        self.test_server.db.insert_documents("tba_tim", tba_tims)
        self.test_calc.run()
        result = self.test_server.db.find("tba_team")
        assert len(result) == 2
        for document in result:
            del document["_id"]
            assert document in expected_results
