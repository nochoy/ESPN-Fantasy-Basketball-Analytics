"""
Google Sheets Export Module
Handles exporting fantasy data to Google Sheets
"""

import os
import pandas as pd
from typing import Dict, Optional
import gspread
from gspread.utils import ValueRenderOption
from google.oauth2.service_account import Credentials
# from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()


class GoogleSheetsExporter:
    """Exporter for sending fantasy data to Google Sheets"""
    
    # Google Sheets API scopes needed
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_path: Optional[str] = None, sheet_name: Optional[str] = None):
        """
        Initialize Google Sheets exporter
        
        Args:
            credentials_path: Path to service account JSON file
            sheet_name: Name of the Google Sheet to create/use
        """
        self.credentials_path = credentials_path or os.getenv('GOOGLE_CREDENTIALS_PATH', './config/google-credentials.json')
        print("***************init PRE sheet_name: ", sheet_name)
        # print("***************init PRE folder_id: ", folder_id)

        self.sheet_name = sheet_name or os.getenv('GOOGLE_SHEET_NAME', 'ESPN Fantasy Basketball Analytics')
        # self.folder_id = folder_id or os.getenv('GOOGLE_FOLDER_ID', None)
        
        print("***************init AFTER sheet_name: ", self.sheet_name)
        # print("***************init AFTER folder_id: ", self.folder_id)
        self.client = None
        self.sheet = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Sheets API"""
        try:
            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.SCOPES
            )
            self.client = gspread.authorize(credentials)
            print(f"✓ Authenticated with Google Sheets")
        except Exception as e:
            raise AuthenticationError(f"Failed to authenticate with Google Sheets: {e}")
    
    def get_sheet(self) -> gspread.Spreadsheet:
        """
        Get existing sheet or create new one
        
        Returns:
            gspread Spreadsheet object
        """
        try:
            # Try to open existing sheet
            self.sheet = self.client.open(self.sheet_name)
            print(f"✓ Opened existing sheet: '{self.sheet_name}'")
        except gspread.SpreadsheetNotFound:
            print("Cannot find sheet: ", self.sheet_name)
            # Create new sheet

            # if self.folder_id:
            #     self.sheet = self.client.create(self.sheet_name, folder_id=self.folder_id)
            # else:
            #     self.sheet = self.client.create(self.sheet_name)  # Creates in service account Drive
            
            # print(f"✓ Created new sheet: '{self.sheet_name}'")

            # # Share with user if email is in env
            # user_email = os.getenv('GOOGLE_USER_EMAIL')
            # if user_email:
            #     self.sheet.share(user_email, perm_type='user', role='writer')
            #     print(f"  Shared with {user_email}")
        
        return self.sheet
    
    def clear_all_worksheets(self):
        """Clear all existing worksheets except the default one"""
        worksheets = self.sheet.worksheets()
        
        # Keep first worksheet, delete others
        for ws in worksheets[1:]:
            self.sheet.del_worksheet(ws)
        
        # Clear first worksheet
        if worksheets:
            worksheets[0].clear()
            worksheets[0].update_title('Overview')
    
    def create_worksheet(self, title: str, rows: int = 300, cols: int = 20) -> gspread.Worksheet:
        """
        Create a new worksheet
        
        Args:
            title: Worksheet title
            rows: Number of rows
            cols: Number of columns
            
        Returns:
            gspread Worksheet object
        """
        try:
            # Try to get existing worksheet
            return self.sheet.worksheet(title)
        except gspread.WorksheetNotFound:
            # Create new worksheet
            return self.sheet.add_worksheet(title=title, rows=rows, cols=cols)
    
    def write_dataframe(self, worksheet: gspread.Worksheet, df: pd.DataFrame, 
                       start_cell: str = 'A1', include_index: bool = False):
        """
        Write a pandas DataFrame to a worksheet
        
        Args:
            worksheet: gspread Worksheet object
            df: pandas DataFrame
            start_cell: Starting cell (A1 notation)
            include_index: Whether to include DataFrame index
        """
        # Convert DataFrame to list of lists
        if include_index:
            data = [df.columns.tolist()] + df.reset_index().values.tolist()
        else:
            data = [df.columns.tolist()] + df.values.tolist()
        
        # Clear the worksheet first
        worksheet.clear()
        
        # Write data
        worksheet.update(data, start_cell)
        
        # Format header row
        worksheet.format('1:1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
        })
    
    def format_standings(self, worksheet: gspread.Worksheet, num_rows: int):
        """Apply special formatting to standings sheet"""
        # Format top 3 rows with gold/silver/bronze colors
        formats = [
            ('2:2', {'backgroundColor': {'red': 1, 'green': 0.84, 'blue': 0}}),  # Gold
            ('3:3', {'backgroundColor': {'red': 0.75, 'green': 0.75, 'blue': 0.75}}),  # Silver
            ('4:4', {'backgroundColor': {'red': 0.8, 'green': 0.5, 'blue': 0.2}}),  # Bronze
        ]
        
        for range_str, format_dict in formats:
            try:
                worksheet.format(range_str, format_dict)
            except:
                pass  # Row might not exist
    
    def export_all_stats(self, stats: Dict[str, pd.DataFrame]):
        """
        Export all statistics to Google Sheets (matching main.py output)
        
        Args:
            stats: Dictionary of DataFrames with calculated stats
        """
        print("\nExporting to Google Sheets...")
        
        # Get or create sheet
        self.get_sheet()
        
        # 1. Standings (full data)
        ws_standings = self.create_worksheet('Standings')
        self.write_dataframe(ws_standings, stats['standings'])
        self.format_standings(ws_standings, len(stats['standings']))
        print("  ✓ Exported: Standings")
        
        # 2. Weekly Rankings (full data)
        ws_weekly = self.create_worksheet('Weekly Rankings')
        self.write_dataframe(ws_weekly, stats['weekly_rankings'])
        print("  ✓ Exported: Weekly Rankings")
        
        # 3. Cumulative Stats (full data)
        ws_cumulative = self.create_worksheet('Cumulative Stats')
        self.write_dataframe(ws_cumulative, stats['cumulative_stats'])
        print("  ✓ Exported: Cumulative Stats")
        
        # 4. Injury Stats Summary (grouped by team)
        injury_summary = stats['injury_stats'].groupby(['team_id', 'team_name']).agg({
            'avg_games_missed_injury': 'last',
            'avg_games_missed_ir': 'last',
            'avg_total_games_missed': 'last',
            'avg_lost_points_injury': 'last',
            'avg_lost_points_ir': 'last',
            'avg_total_lost_points': 'last',
            'games_missed_injury': 'sum',
            'games_missed_ir': 'sum',
            'total_games_missed': 'sum',
            'lost_points_injury': 'sum',
            'lost_points_ir': 'sum',
            'total_lost_points': 'sum',
        }).reset_index()
        injury_summary = injury_summary.sort_values('total_games_missed', ascending=False)
        
        ws_injury_summary = self.create_worksheet('Injury Summary')
        self.write_dataframe(ws_injury_summary, injury_summary)
        print("  ✓ Exported: Injury Summary")
        
        # 5. Injury Stats Weekly (grouped by week/team)
        injury_weekly = stats['injury_stats'].groupby(['week', 'team_id', 'team_name']).sum().reset_index()
        ws_injury_weekly = self.create_worksheet('Injury Weekly')
        self.write_dataframe(ws_injury_weekly, injury_weekly)
        print("  ✓ Exported: Injury Weekly")
        
        # 6. Toughest Opponents (grouped by team)
        toughness_summary = stats['toughest_opponents'].groupby(['team_name', 'team_id'])['cumulative_avg_opp_rank'].last().sort_values().reset_index()
        ws_toughness = self.create_worksheet('Toughest Opponents')
        self.write_dataframe(ws_toughness, toughness_summary)
        print("  ✓ Exported: Toughest Opponents")
        
        # 7. Toughest Opponents Full Data
        ws_opponents_full = self.create_worksheet('Toughest Opponents Full')
        self.write_dataframe(ws_opponents_full, stats['toughest_opponents'])
        print("  ✓ Exported: Toughest Opponents Full")
        
        # Auto-resize columns for all worksheets
        self._auto_resize_columns()
        
        print(f"\n✓ All data exported to: {self.sheet.url}")

    
    def _auto_resize_columns(self):
        """Auto-resize all columns in all worksheets"""
        for worksheet in self.sheet.worksheets():
            try:
                # Get all data to determine max width needed
                data = worksheet.get_all_values()
                if not data:
                    continue
                
                # Calculate column widths based on content
                num_cols = len(data[0])
                for col_idx in range(1, num_cols + 1):
                    max_length = 0
                    for row in data:
                        if col_idx <= len(row):
                            cell_length = len(str(row[col_idx - 1]))
                            max_length = max(max_length, cell_length)
                    
                    # Set column width (minimum 100 pixels, max 400)
                    pixel_width = min(max(max_length * 8, 100), 400)
                    
                    # Update column width using API
                    try:
                        worksheet.resize_columns(col_idx, pixel_width)
                    except:
                        pass  # Some versions don't support this
                        
            except Exception as e:
                print(f"  Warning: Could not auto-resize {worksheet.title}: {e}")
    
    def create_summary_dashboard(self, stats: Dict[str, pd.DataFrame]):
        """
        Create a summary dashboard with key metrics
        
        Args:
            stats: Dictionary of DataFrames
        """
        print("\nCreating Summary Dashboard...")
        
        # Get first worksheet or create Dashboard
        try:
            ws = self.sheet.worksheet('Dashboard')
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = self.sheet.add_worksheet('Dashboard', rows=50, cols=20)
        
        standings = stats['standings']
        # consistency = stats['consistency']
        # luck = stats['luck_factor'].groupby(['team_id', 'team_name'])['cumulative_luck'].last().reset_index()
        
        # Build dashboard data
        dashboard_data = [['🏀 ESPN Fantasy Basketball Analytics', '', '', '', '']]
        dashboard_data.append(['', '', '', '', ''])
        dashboard_data.append(['📊 Current Standings', '', '', '', ''])
        dashboard_data.append(['Rank', 'Team', 'Record', 'Win %', 'Point Diff'])
        
        for _, row in standings.head(10).iterrows():
            record = f"{row['wins']}-{row['losses']}"
            if row['ties'] > 0:
                record += f"-{row['ties']}"
            dashboard_data.append([
                row['rank'],
                row['team_name'],
                record,
                f"{row['win_pct']:.3f}",
                row['differential']
            ])
        
        dashboard_data.append(['', '', '', '', ''])
        # dashboard_data.append(['🍀 Luckiest Teams (Most Wins Above Expected)', '', '', '', ''])
        # dashboard_data.append(['Team', 'Luck Score', '', '', ''])
        
        # luck_sorted = luck.sort_values('cumulative_luck', ascending=False)
        # for _, row in luck_sorted.head(5).iterrows():
        #     dashboard_data.append([row['team_name'], f"{row['cumulative_luck']:+.2f}", '', '', ''])
        
        # dashboard_data.append(['', '', '', '', ''])
        # dashboard_data.append(['📈 Most Consistent Teams (Low Std Dev)', '', '', '', ''])
        # dashboard_data.append(['Team', 'Avg PF', 'Std Dev', 'Consistency Score', ''])
        
        # consistency_sorted = consistency.sort_values('consistency_score')
        # for _, row in consistency_sorted.head(5).iterrows():
        #     dashboard_data.append([
        #         row['team_name'],
        #         row['avg_pf'],
        #         row['std_pf'],
        #         row['consistency_score'],
        #         ''
        #     ])
        
        # Write dashboard
        ws.update('A1', dashboard_data)
        
        # Format dashboard
        ws.format('A1', {'textFormat': {'bold': True, 'fontSize': 14}})
        ws.format('A3', {'textFormat': {'bold': True}})
        ws.format('A8', {'textFormat': {'bold': True}})
        ws.format('A14', {'textFormat': {'bold': True}})
        
        print("  ✓ Dashboard created")


class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass
