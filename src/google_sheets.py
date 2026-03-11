"""
Google Sheets Export Module
Handles exporting fantasy data to Google Sheets
"""

import os
import pandas as pd
from datetime import date
from typing import Dict, Optional
import gspread
from gspread.utils import ValueRenderOption
from google.oauth2.service_account import Credentials
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
        self.sheet_name = sheet_name or os.getenv('GOOGLE_SHEET_NAME', 'ESPN Fantasy Basketball Analytics')
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
        Get existing sheet or print error
        
        Returns:
            gspread Spreadsheet object
        """
        try:
            self.sheet = self.client.open(self.sheet_name)

            print(f"✓ Opened existing sheet: '{self.sheet_name}'")
        except gspread.SpreadsheetNotFound:
            print("Cannot find sheet: ", self.sheet_name)
        
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
        Return an existing worksheet or create a new worksheet
        
        Args:
            title: Worksheet title
            rows: Number of rows
            cols: Number of columns
            
        Returns:
            gspread Worksheet object
        """
        try:
            return self.sheet.worksheet(title)
        except gspread.WorksheetNotFound:
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
        
        # Write data
        worksheet.update(data, start_cell)
        
        # Format header row
        worksheet.format('1:1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
        })
    
    def export_all_stats(self, stats: Dict[str, pd.DataFrame]):
        """
        Export all statistics to Google Sheets
        
        Args:
            stats: Dictionary of DataFrames with calculated stats
        """
        print("\nExporting to Google Sheets...")
        
        self.get_sheet()
        
        # 1. Standings (standings + injury stats + toughness stats)
        standings = stats['standings']

        injury_standings = stats['injury_stats'].groupby(['team_id', 'team_name']).agg({
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

        toughness_standings = stats['cumulative_stats'].groupby(['team_name', 'team_id'])['cumulative_pa_rank'].last().sort_values().reset_index()

        standings_and_injury_df = pd.merge(standings, injury_standings, on=['team_id', 'team_name'], how='outer')
        master_standings = pd.merge(standings_and_injury_df, toughness_standings, on=['team_id', 'team_name'], how='outer')

        master_standings_col_order = [
            'team_name', 'team_id', 'rank', 'wins', 'losses', 'ties', 'win_pct', 
            'total_pf', 'total_pa', 'differential', 'avg_opponent_rank', 'cumulative_pa_rank', 
            'avg_pf', 'avg_pa', 'avg_differential',
            'games_missed_injury', 'games_missed_ir', 'total_games_missed', 
            'lost_points_injury', 'lost_points_ir', 'total_lost_points', 
            'avg_games_missed_injury', 'avg_games_missed_ir', 'avg_total_games_missed', 
            'avg_lost_points_injury', 'avg_lost_points_ir', 'avg_total_lost_points'
        ]

        master_standings = master_standings[master_standings_col_order].sort_values('rank')

        ws_standings = self.create_worksheet('Standings', len(master_standings), len(master_standings_col_order))
        self.write_dataframe(ws_standings, master_standings, start_cell='A2')
        print("  ✓ Exported: Standings")
        
        # 2. Weekly Rankings (weekly ranks + cumulative stats + injury stats + toughness stats)
        weekly_rankings = stats['weekly_rankings']
        cumulative_stats = stats['cumulative_stats']
        injury_weekly = stats['injury_stats'].groupby(['week', 'team_id', 'team_name']).sum().reset_index()

        weekly_and_cumulative_df = pd.merge(weekly_rankings, cumulative_stats, on=['week', 'team_id', 'team_name'], how='outer')
        master_weekly_rankings = pd.merge(weekly_and_cumulative_df, injury_weekly, on=['week', 'team_id', 'team_name'], how='outer')

        master_weekly_col_order = [
            'week', 'team_name', 'team_id', 'opponent_name', 'rank', 'wins', 'losses', 'win_pct', 
            'pf', 'pa', 'differential', 'pf_rank', 'pa_rank', 
            'cumulative_pf', 'cumulative_pa', 'cumulative_differential', 'cumulative_pf_rank', 'cumulative_pa_rank', 
            'games_missed_injury', 'games_missed_ir', 'total_games_missed', 
            'lost_points_injury', 'lost_points_ir', 'total_lost_points', 
            'cumulative_games_missed_injury', 'cumulative_games_missed_ir', 'cumulative_total_games_missed', 
            'cumulative_lost_points_injury', 'cumulative_lost_points_ir', 'cumulative_total_lost_points'
        ]

        master_weekly_rankings = master_weekly_rankings[master_weekly_col_order]

        ws_weekly = self.create_worksheet('Weekly Rankings', len(master_weekly_rankings), len(master_weekly_col_order))
        self.write_dataframe(ws_weekly, master_weekly_rankings, start_cell='A2')
        print("  ✓ Exported: Weekly Rankings")
        
        print(f"\n✓ All data exported to: {self.sheet.url}")
    
    def create_overview(self, stats: Dict[str, pd.DataFrame]):
        """
        Create a comprehensive overview with an introduction, changelog, 
        features to add, tips for analyzing, and detailed metric documentation.
        """
        
        try:
            self.get_sheet()
            ws = self.sheet.worksheet('Overview')
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = self.sheet.add_worksheet('Overview', rows=50, cols=13)
                
        left_data = []      # columns A-G
        right_data = []     # columns H-J
        version = 1.0
        today = date.today()
        
        # Welcome
        left_data.append(['📖 WELCOME', '', '', '', '', '', ''])
        left_data.append(['This dashboard provides an overview of this spreadsheet to help viewers quickly understand how to read'])
        left_data.append(['and interact with this spreadsheet and explains how metrics are calculated.'])
        left_data.append(['This doc displays results (W/L, ranks), tracks performance (PF/PA, differential, cumulative production),'])
        left_data.append(['and provides context (strength of schedule and injury impact.'])
        left_data.append(['This spreadsheet is divided into 2 pages: Standings and Weekly Rankings', '', '', '', ''])

        left_data.append(['', '', '', '', '', '', ''])
        # SHEET OVERVIEW
        left_data.append(['📊 SHEET OVERVIEW', '', '', '', '', '', ''])
        left_data.append(['Sheet Name', 'Description', '', '', '', '', ''])
        left_data.append(['Standings', 'Current league standings with season-long aggregated stats.', '', '', '', '', ''])
        left_data.append(['Weekly Rankings', 'Week-by-week breakdown for each team', '', '', '', '', ''])
        left_data.append(['', '', '', '', '', '', ''])
        left_data.append(['', '', '', '', '', '', ''])
        left_data.append(['', '', '', '', '', '', ''])
        
        # CHANGE LOG
        right_data.append(['📝 CHANGE LOG', '', '', '', ''])
        right_data.append(['Date', 'Version', 'Changes', '', ''])
        right_data.append(['2026-02-27', 0.1, 'Finished adding conditional formatting rules', '', ''])
        right_data.append([str(today), str(version), 'Initial release with Overview, Standings, and Weekly Rankings pages', '', ''])
        right_data.append(['', '', '', '', '', '', ''])
        
        # FEATURES TO ADD
        right_data.append(['🚀 STATS/FEATURES TO ADD', '', '', '', ''])
        right_data.append(['Win/loss margins (differential)'])
        right_data.append(['Games played'])
        right_data.append(['Avg PF/PA for wins/losses'])
        right_data.append(['Potential wins (add lost points due to benched players and/or injured players)'])
        right_data.append(['Experiments (if players were healthy, if didnt leave player on bench, if had easiest schedule, etc.)'])
        right_data.append(['Superlatives (biggest winner, biggest blowout, clutch, etc.)'])
        right_data.append(['lost_points_injury - use projected avg FPTS if season\'s avg FPTS = 0', '', '', '', ''])
        right_data.append(['', '', '', '', ''])
        
        # KEY METRICS EXPLAINED
        left_data.append(['🔍 KEY METRICS EXPLAINED', '', '', '', ''])
        left_data.append(['Column', 'Description', '', '', '', 'How It\'s Calculated', '', '']) # col A, B, F

        left_data.append(['rank', 'Current standing in the league', '', '', '', 'Based on wins, then total points for PF (ESPN does wins -> H2H matchups -> PF)', '', ''])
        left_data.append(['total_pf', 'Total points scored', '', '', '', 'Sum of all fantasy points scored across all weeks', '', ''])
        left_data.append(['total_pa', 'Total points opponents\' scored against', '', '', '', 'Sum of all fantasy points scored against you', '', ''])
        left_data.append(['differential', 'Point differential', '', '', '', 'total_pf - total_pa (positive = scoring more than allowing)', '', ''])
        left_data.append(['avg_opponent_rank', 'Average opponent rank in standings', '', '', '', 'Average rank of opponents faced, based on latest standings (lower = tougher schedule)', '', ''])
        left_data.append(['cumulative_pa_rank', 'Running average of pa rank', '', '', '', 'Running average of opponent\'s PF rank for each week (lower = tougher schedule, stronger indicator of Strength of Schedule (Sos))', '', ''])
        left_data.append(['cumulative_pf_rank', 'Running average of pf rank', '', '', '', 'Running average of PF rank for each week', '', ''])
        left_data.append(['games_missed_injury', 'Number of games missed due to injury, NOT including IR', '', '', '', 'Checks if player had scheduled opponent + scored 0 FPTS + recorded no stats (counts DNPs) + not on IR', '', ''])
        left_data.append(['games_missed_r', 'Number of games missed due to injury ON IR', '', '', '', 'Checks if player had scheduled opponent + scored 0 FPTS + recorded no stats (counts DNPs) + on IR', '', ''])
        left_data.append(['total_games_missed', 'Total number of games missed due to injury', '', '', '', 'Sum of games_missed_injury + games_missed_ir', '', ''])
        left_data.append(['lost_points_injury', 'Potential points lost due to player being injured, NOT on IR', '', '', '', 'Based on player\'s average FPTS on the season', '', ''])
        left_data.append(['lost_points_ir', 'Potential points lost due to player being injured, ON IR', '', '', '', 'Based on player\'s average FPTS on the season', '', ''])
        left_data.append(['total_lost_points', 'Total potential points lost due to player being injured', '', '', '', 'Sum of lost_points_injury + lost_points_ir', '', ''])
        left_data.append(['avg_total_games_missed', 'Average games missed due to injury', '', '', '', 'total_games_missed divided by the number of weeks', '', ''])
        left_data.append(['avg_total_lost_points', 'Average potential points lost due to injury', '', '', '', 'total_lost_points divided by the number of weeks', '', ''])
        left_data.append(['cumulative_total_games_missed', 'Cumulative total of games missed due to injury', '', '', '', 'Sum of total_games_missed up to that week', '', ''])
        left_data.append(['cumulative_total_lost_points', 'Cumulative total of potential points lost due to injury', '', '', '', 'Sum of total_lost_points up to that week', '', ''])
        left_data.append(['', '', '', '', '', '', ''])

        
        # Tips
        left_data.append(['💡 TIPS FOR ANALYZING:', '', '', '', '', '', ''])
        left_data.append(['- View sheet on Desktop to make use of Google Sheet\'s table views (not available on Mobile)', '', '', '', '', '', ''])
        left_data.append(['- Use preloaded table views to view grouped or sorted data (will not affect other viewers)', '', '', '', '', '', ''])
        left_data.append(['- Recommend using "Group By Week" table view for Weekly Rankings ', '', '', '', '', '', ''])
        left_data.append(['- Create your own private table view to sort/group data in whatever way you want, which does not affect the sheet or other viewers at all', '', '', '', '', '', ''])
        left_data.append(['- Lower rank numbers indicate stronger/higher stats (1st place is rank 1)', '', '', '', '', '', ''])
        left_data.append(['- SoS - cumulative_pa_rank is a strong indicator of schedule difficulty as it includes week-by-week context', '', '', '', '', '', ''])
        left_data.append(['- Color scales are added for context, making it easier to compare stats and view change over the course of the season. Green indicates favorable data for the player (higher PF, lower PA, less injuries, lower SoS, etc.)', '', '', '', '', '', ''])
        left_data.append(['- Color scales are independent for each week, except for rank, pf_rank, pa_rank, cumulative_pf_rank, cumulative_pa_rank (color scale used for entire col)', '', '', '', '', '', ''])
        left_data.append(['- Bolded stats indicate column max', '', '', '', '', '', ''])
        left_data.append(['- Green highlighed teams (leftmost col) in Weekly Rankings indicate a win for that week', '', '', '', '', '', ''])
        left_data.append(['- Add comments for suggestions or fixes', '', '', '', '', '', ''])
        left_data.append(['', '', '', '', '', '', ''])
        
        # Write to sheet
        ws.update('A1', left_data)
        ws.update('H1', right_data)
        
        # Format headers
        header_rows = ['A1', 'A8', 'A15', 'A35', 'H1', 'H6']
        for cell in header_rows:
            ws.format(cell, {'textFormat': {'bold': True, 'fontSize': 12}})

        # Format subheaders
        bolded_cells = ['A9', 'A10', 'A11', 'B9', 'A16', 'B16', 'E16', 'H2', 'I2', 'J2', ]
        for cell in bolded_cells:
            ws.format(cell, {'textFormat': {'bold': True}})
        
        print("  ✓ Overview page created with changelog, features, and documentation")


class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass
