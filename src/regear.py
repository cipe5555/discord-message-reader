import requests
import re
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from dateutil import parser
from collections import defaultdict
import os
from dotenv import load_dotenv
import json

class RegearAgent:
    def __init__(self):
        load_dotenv()
        self.QUALITY_MAP = {
            "1": "無",
            "2": "鉄",
            "3": "銅",
            "4": "銀",
            "5": "金"
        }
        self.SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
        service_account_json = os.getenv("GOOGLE_SERVICE_KEY")

        if not self.SHEET_URL or not service_account_json:
            raise ValueError("Missing Google Sheets URL or service account key in environment variables!")
        
        service_account_info = json.loads(service_account_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        self.creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    
    def regear(self, start_time, end_time, sheet_name):
        client = gspread.authorize(self.creds)
        spreadsheet = client.open_by_url(self.SHEET_URL)

        # Create or get new sheet tabs
        raw_data_sheet_name = f"{sheet_name}_Raw"
        statistics_sheet_name = f"{sheet_name}_Statistics"
        
        try:
            raw_data_sheet = spreadsheet.worksheet(raw_data_sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            raw_data_sheet = spreadsheet.add_worksheet(title=raw_data_sheet_name, rows="1000", cols="10")
            raw_data_sheet.append_row(["Timestamp", "Name", "Main Hand", "Off Hand", "Head", "Armor", "Shoes", "Cape", "Mount"])
        
        try:
            statistics_sheet = spreadsheet.worksheet(statistics_sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            statistics_sheet = spreadsheet.add_worksheet(title=statistics_sheet_name, rows="1000", cols="2")
            statistics_sheet.append_row(["Item Name", "Count"])
        
        members_data_sheet = spreadsheet.worksheet("Members")
        raw_items_sheet = spreadsheet.worksheet("RawItems")

        raw_items_data = raw_items_sheet.get_all_records()
        item_name_map = {row["Unique Item Name"]: row["Base Item Name"] for row in raw_items_data if row["Unique Item Name"]}

        form_data = members_data_sheet.get_all_records()
        player_names = {
            str(row["Guild Members"]).strip().lower()
            for row in form_data 
            if isinstance(row.get("Guild Members"), str) and row["Guild Members"].strip()
        }

        item_counts = defaultdict(int)

        def get_item_details(item):
            if not item:
                return "None"
            
            unique_name = item.get("Type", "None")
            quality = str(item.get("Quality", "0"))
            quality_label = self.QUALITY_MAP.get(quality, "none")

            match = re.match(r"(T\d+)_?(.*?)(@\d+)?$", unique_name)
            if match:
                tier, base_name, level_suffix = match.groups()
                level = f".{level_suffix[1:]}" if level_suffix else ""
                localized_name = item_name_map.get(unique_name, base_name)
                item_full_name = f"{localized_name}{tier}{level} - {quality_label}"
                item_counts[item_full_name] += 1
                return item_full_name
            else:
                localized_name = item_name_map.get(unique_name, "")
                item_full_name = f"{localized_name} - {quality_label}"
                item_counts[item_full_name] += 1
                return item_full_name

        guild_url = "https://gameinfo-sgp.albiononline.com/api/gameinfo/guilds/Oyx4dxj1RWGDV5Pf_o4XTg/members"
        response = requests.get(guild_url)

        if response.status_code == 200:
            guild_data = response.json()
            if isinstance(guild_data, list):
                new_rows = []
                for player in guild_data:
                    name = player.get("Name", "").strip()
                    player_id = player.get("Id", "")
                    if name.lower() in player_names:
                        print(f"Processing player: {name}")
                        deaths_url = f"https://gameinfo-sgp.albiononline.com/api/gameinfo/players/{player_id}/deaths"
                        deaths_response = requests.get(deaths_url)
                        if deaths_response.status_code == 200:
                            deaths_data = deaths_response.json()
                            for death in deaths_data:
                                timestamp_str = death.get("TimeStamp", "")
                                timestamp = parser.isoparse(timestamp_str).replace(tzinfo=None)
                                if start_time <= timestamp <= end_time:
                                    victim = death.get("Victim", {})
                                    equipment = victim.get("Equipment", {})
                                    new_rows.append([
                                        timestamp_str,
                                        name,
                                        get_item_details(equipment.get("MainHand")),
                                        get_item_details(equipment.get("OffHand")),
                                        get_item_details(equipment.get("Head")),
                                        get_item_details(equipment.get("Armor")),
                                        get_item_details(equipment.get("Shoes")),
                                        get_item_details(equipment.get("Cape")),
                                        get_item_details(equipment.get("Mount"))
                                    ])
                        else:
                            print(f"Error fetching death history for {name} (Status Code: {deaths_response.status_code})")
                if new_rows:
                    raw_data_sheet.append_rows(new_rows)
                    print(f"{len(new_rows)} rows added to '{raw_data_sheet_name}' sheet.")
            else:
                print("Unexpected response format")
        else:
            print(f"Error: Unable to fetch data (Status Code: {response.status_code})")

        statistics_sheet.clear()
        statistics_sheet.append_row(["Item Name", "Count"])
        sorted_statistics_data = sorted(item_counts.items())
        if sorted_statistics_data:
            statistics_sheet.append_rows(sorted_statistics_data)
        print("Statistics updated successfully!")
