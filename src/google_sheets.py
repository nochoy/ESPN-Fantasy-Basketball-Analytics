"""
Google Sheets Export Module
Handles exporting fantasy data to Google Sheets
"""

import os
import pandas as pd
from datetime import date
from typing import Dict, List, Optional
import gspread
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from config.formatting_config import STANDINGS_FORMATTING, WEEKLY_FORMATTING

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
        self.credentials_path = credentials_path or os.getenv('GOOGLE_CREDENTIALS_PATH', './src/config/google-credentials.json')
        self.sheet_name = sheet_name or os.getenv('GOOGLE_SHEET_NAME', 'ESPN Fantasy Basketball Analytics')
        self.client = None
        self.sheet = None
        self.stats = {}
        self.data_start_row = 3
        self.format_requests = []
        self.standings_col_map = {}
        self.weekly_rankings_col_map = {}

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
    
    def clear_all_conditional_formatting(self):
        """
        Remove all conditional formatting rules from every sheet.
        """

        metadata = self.sheet.fetch_sheet_metadata()
        requests = []

        for sheet in metadata["sheets"]:
            sheet_id = sheet["properties"]["sheetId"]

            rules = sheet.get("conditionalFormats", [])
            for index in reversed(range(len(rules))):
                requests.append({
                    "deleteConditionalFormatRule": {
                        "sheetId": sheet_id,
                        "index": index
                    }
                })

        if requests:
            self.sheet.batch_update({"requests": requests})
            print(f"  ✓ Cleared {len(requests)} conditional formatting rules")

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
    
    def _compile_standings_df(self) -> pd.DataFrame:
        """
        Compile statistics for Standings page into dataframe ready for export
        """

        print("  Compiling stats for Standings page to export...")

        standings = self.stats['standings']
        injury_standings = self.stats['injury_stats'].groupby(['team_id', 'team_name']).agg({
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

        toughness_standings = self.stats['cumulative_stats'].groupby(['team_name', 'team_id'])['cumulative_pa_rank'].last().sort_values().reset_index()

        # Merge data into one sheet
        standings_and_injury_df = pd.merge(standings, injury_standings, on=['team_id', 'team_name'], how='outer')
        standings_and_efficiency_df = pd.merge(standings_and_injury_df, self.stats['efficiency_summary'], on=['team_id', 'team_name'], how='outer')
        full_standings_df = pd.merge(standings_and_efficiency_df, toughness_standings, on=['team_id', 'team_name'], how='outer')

        # Reorder columns
        full_standings_df_col_order = [
            'team_name', 'team_id', 'rank', 'wins', 'losses', 'ties', 'win_pct', 
            'total_pf', 'total_pa', 'differential', 'avg_opponent_rank', 'cumulative_pa_rank', 
            'avg_pf', 'avg_pa', 'avg_differential',
            'games_missed_injury', 'games_missed_ir', 'total_games_missed', 
            'lost_points_injury', 'lost_points_ir', 'total_lost_points', 
            'avg_games_missed_injury', 'avg_games_missed_ir', 'avg_total_games_missed', 
            'avg_lost_points_injury', 'avg_lost_points_ir', 'avg_total_lost_points',
            'player_games', 'bench_games', 'ir_games', 'total_missed_games',
            'bench_points_lost', 'ir_points_lost', 'total_points_lost',
            'avg_player_games', 'avg_bench_games', 'avg_ir_games', 'avg_total_missed_games',
            'avg_bench_points_lost', 'avg_ir_points_lost', 'avg_total_points_lost',
        ]
        full_standings_df = full_standings_df[full_standings_df_col_order].sort_values('rank')

        # Build col map for formatting
        self.standings_col_map = self._build_col_map(full_standings_df)

        return full_standings_df
    
    def _compile_weekly_rankings_df(self) -> pd.DataFrame:
        """
        Compile statistics for Weekly Rankings page into dataframe ready for export
        """

        print("  Compiling stats for Weekly Rankings page to export...")

        weekly_rankings = self.stats['weekly_rankings']
        cumulative_stats = self.stats['cumulative_stats']
        injury_weekly = self.stats['injury_stats'].groupby(['week', 'team_id', 'team_name']).sum().reset_index()

        # Merge datra into one sheet
        weekly_and_cumulative_df = pd.merge(weekly_rankings, cumulative_stats, on=['week', 'team_id', 'team_name'], how='outer')
        weekly_and_efficiency_df = pd.merge(weekly_and_cumulative_df, self.stats['efficiency_stats'], on=['week', 'team_id', 'team_name'], how='outer')
        full_weekly_rankings_df = pd.merge(weekly_and_efficiency_df, injury_weekly, on=['week', 'team_id', 'team_name'], how='outer')

        # Reorder columns
        master_weekly_col_order = [
            'week', 'team_name', 'team_id', 'opponent_name', 'rank', 'wins', 'losses', 'win_pct', 
            'pf', 'pa', 'differential', 'pf_rank', 'pa_rank', 
            'cumulative_pf', 'cumulative_pa', 'cumulative_differential', 'cumulative_pf_rank', 'cumulative_pa_rank', 
            'games_missed_injury', 'games_missed_ir', 'total_games_missed', 
            'lost_points_injury', 'lost_points_ir', 'total_lost_points', 
            'cumulative_games_missed_injury', 'cumulative_games_missed_ir', 'cumulative_total_games_missed', 
            'cumulative_lost_points_injury', 'cumulative_lost_points_ir', 'cumulative_total_lost_points',
            'player_games', 'bench_games', 'ir_games', 'total_missed_games',
            'bench_points_lost', 'ir_points_lost', 'total_points_lost',
        ]
        full_weekly_rankings_df = full_weekly_rankings_df[master_weekly_col_order]

        # Build col map for formatting
        self.weekly_rankings_col_map = self._build_col_map(full_weekly_rankings_df)

        return full_weekly_rankings_df

    def export_all_stats(self, stats: Dict[str, pd.DataFrame]):
        """
        Export all statistics to Google Sheets
        
        Args:
            stats: Dictionary of DataFrames with calculated stats
        """
        print("\nExporting to Google Sheets...")

        self.stats = stats
        self.get_sheet()
        self.clear_all_conditional_formatting()

        # Compile Standings page stats, export to Google sheet, and add formatting rules
        full_standings_df = self._compile_standings_df()
        standings_ws = self.create_worksheet('Standings', len(full_standings_df)+self.data_start_row, len(full_standings_df.columns))
        self.write_dataframe(standings_ws, full_standings_df, start_cell='A2')
        self.format_standings(standings_ws, len(full_standings_df), len(full_standings_df.columns))

        print("  ✓ Exported: Standings")
        
        # Compile Weekly Rankings page stats, export to Google sheet, and apply formatting
        full_weekly_rankings_df = self._compile_weekly_rankings_df()
        ws_weekly = self.create_worksheet('Weekly Rankings', len(full_weekly_rankings_df) + self.data_start_row + 1, len(full_weekly_rankings_df.columns))
        self.write_dataframe(ws_weekly, full_weekly_rankings_df, start_cell='A2')
        self.format_weekly_rankings(ws_weekly, len(full_standings_df), len(full_weekly_rankings_df.columns), full_weekly_rankings_df['week'].max())

        print("  ✓ Exported: Weekly Rankings")

        self.apply_all_formatting()
        print(f"\n✓ All data exported to: {self.sheet.url}")
    
    def create_overview(self):
        """
        Create a comprehensive overview with an introduction, changelog, 
        features to add, tips for analyzing, and detailed metric documentation.
        """
        
        try:
            self.get_sheet()
            ws = self.sheet.worksheet('Overview')
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = self.sheet.add_worksheet('Overview', rows=55, cols=13)
                
        left_data = []      # columns A-G
        right_data = []     # columns H-J
        version = 1.1
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
        left_data.append(['📊 SHEET OVERVIEW', '', '', '', '', '', ''])     # col A
        left_data.append(['Sheet Name', 'Description', '', '', '', '', '']) # cols A, B
        left_data.append(['Standings', 'Current league standings with season-long aggregated stats.', '', '', '', '', ''])
        left_data.append(['Weekly Rankings', 'Week-by-week breakdown for each team', '', '', '', '', ''])
        left_data.append(['', '', '', '', '', '', ''])
        left_data.append(['', '', '', '', '', '', ''])
        left_data.append(['', '', '', '', '', '', ''])
        
        # CHANGE LOG
        right_data.append(['📝 CHANGE LOG', '', '', '', ''])        # col H
        right_data.append(['Date', 'Version', 'Changes', '', ''])   # cols H, I, J
        right_data.append(['2026-02-27', 0.1, 'Finished adding conditional formatting rules', '', ''])
        right_data.append(['2026-03-01', 1.0, 'Initial release with Overview, Standings, and Weekly Rankings pages', '', ''])
        right_data.append([str(today), str(version), 'Added Full Season stats + Lineup Efficiency stats, including points lost to players left on BE/IR', '', ''])
        right_data.append(['', '', '', '', '', '', ''])
        
        # FEATURES TO ADD
        right_data.append(['🚀 STATS/FEATURES TO ADD', '', '', '', '']) # col H
        right_data.append(['Win/loss margins (differential)'])
        right_data.append(['✅ Games played'])
        right_data.append(['Avg PF/PA for wins/losses'])
        right_data.append(['Potential wins (add lost points due to benched players and/or injured players)'])
        right_data.append(['Experiments (if players were healthy, if didnt leave player on bench, if had easiest schedule, etc.)'])
        right_data.append(['Superlatives (biggest winner, biggest blowout, clutch, etc.)'])
        right_data.append(['lost_points_injury - use projected avg FPTS if season\'s avg FPTS = 0', '', '', '', ''])
        right_data.append(['', '', '', '', ''])
        
        # KEY METRICS EXPLAINED
        left_data.append(['🔍 KEY METRICS EXPLAINED', '', '', '', ''])
        left_data.append(['Column', '', 'Description', '', '', '', 'How It\'s Calculated', '', '']) # col A, C, G

        left_data.append(['rank', '', 'Current standing in the league', '', '', '', 'Based on wins, then total points for PF (ESPN does wins -> H2H matchups -> PF)', '', ''])
        left_data.append(['total_pf', '', 'Total points scored', '', '', '', 'Sum of all fantasy points scored across all weeks', '', ''])
        left_data.append(['total_pa', '', 'Total points opponents\' scored against', '', '', '', 'Sum of all fantasy points scored against you', '', ''])
        left_data.append(['differential', '', 'Point differential', '', '', '', 'total_pf - total_pa (positive = scoring more than allowing)', '', ''])
        left_data.append(['avg_opponent_rank', '', 'Average opponent rank in standings', '', '', '', 'Average rank of opponents faced, based on latest standings (lower = tougher schedule)', '', ''])
        left_data.append(['cumulative_pa_rank', '', 'Running average of pa rank', '', '', '', 'Running average of opponent\'s PF rank for each week (lower = tougher schedule, stronger indicator of Strength of Schedule (Sos))', '', ''])
        left_data.append(['cumulative_pf_rank', '', 'Running average of pf rank', '', '', '', 'Running average of PF rank for each week', '', ''])
        left_data.append(['games_missed_injury', '', 'Number of games missed due to injury, NOT including IR', '', '', '', 'Checks if player had scheduled opponent + scored 0 FPTS + recorded no stats (counts DNPs) + not on IR', '', ''])
        left_data.append(['games_missed_r', '', 'Number of games missed due to injury ON IR', '', '', '', 'Checks if player had scheduled opponent + scored 0 FPTS + recorded no stats (counts DNPs) + on IR', '', ''])
        left_data.append(['total_games_missed', '', 'Total number of games missed due to injury', '', '', '', 'Sum of games_missed_injury + games_missed_ir', '', ''])
        left_data.append(['lost_points_injury', '', 'Potential points lost due to player being injured, NOT on IR', '', '', '', 'Based on player\'s average FPTS on the season', '', ''])
        left_data.append(['lost_points_ir', '', 'Potential points lost due to player being injured, ON IR', '', '', '', 'Based on player\'s average FPTS on the season', '', ''])
        left_data.append(['total_lost_points', '', 'Total potential points lost due to player being injured', '', '', '', 'Sum of lost_points_injury + lost_points_ir', '', ''])
        left_data.append(['avg_total_games_missed', '', 'Average games missed due to injury', '', '', '', 'total_games_missed divided by the number of weeks', '', ''])
        left_data.append(['avg_total_lost_points', '', 'Average potential points lost due to injury', '', '', '', 'total_lost_points divided by the number of weeks', '', ''])
        left_data.append(['cumulative_total_games_missed', '', 'Cumulative total of games missed due to injury', '', '', '', 'Sum of total_games_missed up to that week', '', ''])
        left_data.append(['cumulative_total_lost_points', '', 'Cumulative total of potential points lost due to injury', '', '', '', 'Sum of total_lost_points up to that week', '', ''])
        left_data.append(['player_games', '', 'Number of active player games that are starting', '', '', '', 'Numbers of starters with points > 0', '', ''])
        left_data.append(['bench_games', '', 'Number of active player games that are left on the bench', '', '', '', 'Numbers of players left on bench with points > 0, if have available starter slots', '', ''])
        left_data.append(['ir_games', '', 'Number of active player games that are left on IR', '', '', '', 'Numbers of players left on IR with points > 0, if have available starter slots', '', ''])
        left_data.append(['bench_points_lost', '', 'Points lost due to player being left on the bench', '', '', '', 'If player on bench has points > 0 and have available starter slots', '', ''])
        left_data.append(['ir_points_lost', '', 'Points lost due to player being left on IR', '', '', '', 'If player on IR has points > 0 and have available starter slots', '', ''])
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
        left_data.append(['- Bolded stats indicate column max (or min for a few cols)', '', '', '', '', '', ''])
        left_data.append(['- Green highlighed teams (leftmost col) in Weekly Rankings indicate a win for that week', '', '', '', '', '', ''])
        left_data.append(['- Add comments for suggestions or fixes', '', '', '', '', '', ''])
        left_data.append(['', '', '', '', '', '', ''])
        
        # Write to sheet
        ws.update('A1', left_data)
        ws.update('H1', right_data)
        
        # Format headers
        header_rows = ['A1', 'A8', 'A15', 'A40', 'H1', 'H7']
        for cell in header_rows:
            ws.format(cell, {'textFormat': {'bold': True, 'fontSize': 12}})

        # Format subheaders
        bolded_cells = ['A9', 'A10', 'A11', 'B9', 'A16', 'C16', 'G16', 'H2', 'I2', 'J2', ]
        for cell in bolded_cells:
            ws.format(cell, {'textFormat': {'bold': True}})
        
        print("  ✓ Overview page created with changelog, features, and documentation")




    def _build_col_map(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        Create mapping of column_name -> 1-based column index (Google Sheets style)
        """

        return {col: i+1 for i, col in enumerate(df.columns)}
    
    def _col_names_to_nums(self, col_map: Dict[str, int], col_names: List[str]) -> List[int]:
        """
        Return list of column numbers from column names
        
        Args:
            col_map: mapping of column names to column numbers
            col_names: list of column names to convert
        """

        return [col_map[n] for n in col_names if n in col_map]

    def apply_all_formatting(self):
        """
        Apply all queued formatting requests
        """

        if not self.format_requests: 
            return
        
        body = {"requests": self.format_requests}
        self.sheet.batch_update(body)

        print(f"  ✓ Applied {len(self.format_requests)} formatting rules")
        self.format_requests = []

    def apply_color_scale(self, worksheet: gspread.Worksheet, 
                          start_row: int = 1, end_row: int = 1, start_col: int = 1, end_col: int = 1, 
                          min_color: Optional[Dict[str, int]] = None, mid_color: Optional[Dict[str, int]] = None, 
                          max_color: Optional[Dict[str, int]] = None, inverse: bool = False):
        """
        Apply color scale conditional formatting, with min=green, max=red by default
        
        Args:
            worksheet: gspread worksheet
            start_row, end_row: Row indices (1-based)
            start_col, end_col: Column indices (1-based, 1=A, 3=C)
            min_color, mid_color, max_color: RGB color dicts
            inverse: bool to swap min & max colors
        """

        if min_color is None:   # green
            min_color = {'red': 0.342, 'green': 0.734, 'blue': 0.542}
        if mid_color is None:   # yellow
            mid_color = {'red': 1.0, 'green': 0.84, 'blue': 0.4}
        if max_color is None:   # red
            max_color = {'red': 0.902, 'green': 0.49, 'blue': 0.451}
            
        if inverse:
            min_color, max_color = max_color, min_color

        request = {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [
                        {
                            "sheetId": worksheet.id,
                            "startRowIndex": start_row-1,
                            "endRowIndex": end_row-1,
                            "startColumnIndex": start_col-1,
                            "endColumnIndex": end_col-1
                        }
                    ],
                    "gradientRule": {
                        'minpoint': {'color': min_color, 'type': 'MIN'},
                        'midpoint': {'color': mid_color, 'type': 'PERCENTILE', 'value': '50'},
                        'maxpoint': {'color': max_color, 'type': 'MAX'}
                    }
                },
                "index": 0
            }
        }

        self.format_requests.append(request)

    def apply_bold_extreme(self, worksheet: gspread.Worksheet, col: int, 
                           start_row: Optional[int] = None, end_row: Optional[int] = None, extreme: str = "max"):
        """
        Apply conditional formatting rule to bold max or min values in a column

        Args:
            worksheet: gspread worksheet
            col: column number of apply conditional formatting rule
            start_row, end_row: Row indices (1-based)
            extreme: bold min or max
        """

        if start_row is None:
            start_row = self.data_start_row
        col_letter = rowcol_to_a1(self.data_start_row, col)[0]

        if extreme == "max":
            formula = f"=${col_letter}{start_row}=MAX(${col_letter}${start_row}:${col_letter}"
        else:
            formula = f"=${col_letter}{start_row}=MIN(${col_letter}${start_row}:${col_letter}"

        if end_row:
            formula += f"${end_row})"
        else:
            formula += ")"

        request = {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": worksheet.id,
                        "startRowIndex": start_row - 1,
                        "endRowIndex": end_row - 1 if end_row is not None else None,
                        "startColumnIndex": col - 1,
                        "endColumnIndex": col
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": formula}]
                        },
                        "format": {
                            "textFormat": {"bold": True}
                        }
                    }
                },
                "index": 0
            }
        }

        self.format_requests.append(request)

    def apply_highlight_win_rows(self, worksheet: gspread.Worksheet, num_cols: int,
                                 start_row: Optional[int] = None, end_row: Optional[int] = None):
        """
        Highlight winner rows in Weekly Rankings page where PF > PA, with green background

        Args:
            worksheet: gspread worksheet
            start_col, end_col: Column indices (1-based, 1=A, 3=C)
            num_cols: number of columns to apply conditional formatting rules to
        """
        
        pf_col_letter = rowcol_to_a1(1, self.weekly_rankings_col_map['pf'])[0]
        pa_col_letter = rowcol_to_a1(1, self.weekly_rankings_col_map['pa'])[0]

        if start_row is None:
            start_row = self.data_start_row
        if end_row is None:
            end_row = start_row + 1

        formula = f"=${pf_col_letter}{start_row}>${pa_col_letter}{start_row}"

        request = {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": worksheet.id,
                        "startRowIndex": start_row - 1,
                        "endRowIndex": end_row - 1 if end_row is not None else None,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": formula}]
                        },
                        "format": {
                            "backgroundColor": {"red": 0.718, "green": 0.883, "blue": 0.804}
                        }
                    }
                },
                "index": 0
            }
        }
        
        self.format_requests.append(request)

    def apply_col_border(self, worksheet: gspread.Worksheet, col: int, start_row: int, end_row: int, border_width: int = 1):
        """
        Add vertical left border at specified column position

        Args:
            worksheet: gspread worksheet
            col: column to set left border
            start_row, end_row: row indices (1-based)
            border_width: width of border
        """

        request = {
            "updateBorders": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": start_row-1,
                    "endRowIndex": end_row-1,
                    "startColumnIndex": col-1,
                    "endColumnIndex": col,
                },
                "left": {
                    "style": "SOLID",
                    "width": border_width
                }
            }
        }

        self.format_requests.append(request)

    def apply_row_border(self, worksheet: gspread.Worksheet, row: int, start_col: int, end_col: int, border_width: int = 1):
        """
        Add horizontal top border at specified row position

        Args:
            worksheet: gspread worksheet
            row: row to set bottom border
            start_col, end_col: column indices (1-based, 1=A, 3=C)
            border_width: width of border
        """

        request = {
            "updateBorders": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": row-1,
                    "endRowIndex": row,
                    "startColumnIndex": start_col-1,
                    "endColumnIndex": end_col-1,
                },
                "top": {
                    "style": "SOLID",
                    "width": border_width
                }
            }
        }

        self.format_requests.append(request)

    def resize_cols(self, worksheet: gspread.Worksheet, column_widths: Dict[int, int]):
        """
         Resize specified columns with the provided column widths
        
         Args:
             worksheet: gspread worksheet
             column_widths: mapping of column nums to pixel widths
         """
        
        for col, width in column_widths.items():
            request = {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": col-1,
                        "endIndex": col,
                    },
                    "properties": {
                        "pixelSize": width,
                    },
                    "fields": "pixelSize",
                }
            }

            self.format_requests.append(request)

    def resize_rows(self, worksheet: gspread.Worksheet, row_heights: Dict[int, int]):
        """
         Resize specified columns with the provided column heights
        
         Args:
             worksheet: gspread worksheet
             row_heights: mapping of row nums to pixel heights
         """
        
        for row, height in row_heights.items():
            request = {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "ROWS",
                        "startIndex": row-1,
                        "endIndex": row,
                    },
                    "properties": {
                        "pixelSize": height,
                    },
                    "fields": "pixelSize",
                }
            }

            self.format_requests.append(request)

    def auto_resize(self, worksheet: gspread.Worksheet, axis: int, index: int):
        """
        Auto resize row or column to fit to data

        Args:
            worksheet: gspread worksheet
            axis: row (0) or column (1) axis 
            index: row number or column number (1-based , A=1, C=3)
        """

        if axis == 0:
            dimension = "ROWS"
        elif axis == 1:
            dimension = "COLUMNS"
        else: 
            return

        request = {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": worksheet.id,
                    "dimension": dimension,
                    "startIndex": index-1,
                    "endIndex": index,
                }
            }
        }
        
        self.format_requests.append(request)

    def set_text_wrap(self, worksheet: gspread.Worksheet, text_wrap: int, start_row: int, end_row: int, start_col: int, end_col: int):
        """
        Set text wrapping strategy to overflow (0), wrap (1), or clip (2) of selected range

        Args:
            text_wrap: overflow (0), wrap (1), or clip (2)
            start_row, end_row: row indices (1-based)
            start_col, end_col: col indices (1-based)
        """

        if text_wrap == 0:
            wrap_strategy = "OVERFLOW"
        elif text_wrap == 1:
            wrap_strategy = "WRAP"
        elif text_wrap == 2:
            wrap_strategy = "CLIP"
        else:
            return
        
        request = {
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": start_row - 1,
                    "endRowIndex": end_row - 1,
                    "startColumnIndex": start_col - 1,
                    "endColumnIndex": end_col - 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "wrapStrategy": wrap_strategy
                    }
                },
                "fields": "userEnteredFormat.wrapStrategy"
            }        
        }

        self.format_requests.append(request)

    def set_alignment(self, worksheet: gspread.Worksheet, axis: int, align: int, start_row: int, end_row: int, start_col: int, end_col: int):
        """
        Set horizontal or vertical alignment strategy
        
        Args:
            axis: horizontal (0), vertical (1)
            align: left/top (0), center/middle (1), right/bottom (2)
            start_row, end_row: row indices (1-based)
            start_col, end_col: col indices (1-based)
        """

        if axis < 0 or axis > 1 or align < 0 or align > 2:
            return

        if align == 0:
            alignment_strategy = "LEFT" if axis == 0 else "TOP"
        elif align == 1:
            alignment_strategy = "CENTER" if axis == 0 else "MIDDLE"
        else:
            alignment_strategy = "RIGHT" if axis == 0 else "BOTTOM"
        
        request = {
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": start_row - 1,
                    "endRowIndex": end_row - 1,
                    "startColumnIndex": start_col - 1,
                    "endColumnIndex": end_col - 1,
                },
            }
        }

        if axis == 0:   # horizontal alignment
            request['repeatCell']['cell'] =  {
                    "userEnteredFormat": {
                        "horizontalAlignment": alignment_strategy,
                    }
                }
            request['repeatCell']['fields'] = "userEnteredFormat(horizontalAlignment)"
        else:           # vertical alignment
            request['repeatCell']['cell'] =  {
                    "userEnteredFormat": {
                        "verticalAlignment": alignment_strategy,
                    }
                }
            request['repeatCell']['fields'] = "userEnteredFormat(verticalAlignment)"
        
        self.format_requests.append(request)

    def merge_cells(self, worksheet: gspread.Worksheet, start_row: int, end_row: int, start_col: int, end_col: int):
        """
        Merge selected cells

        Args:
            start_row, end_row: row indices (1-based)
            start_col, end_col: col indices (1-based)
        """

        request = {
            "mergeCells": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": start_row - 1,
                    "endRowIndex": end_row - 1,
                    "startColumnIndex": start_col - 1,
                    "endColumnIndex": end_col - 1,
                },
                "mergeType": "MERGE_ALL"
            }
        }

        self.format_requests.append(request)

    def freeze_headers(self, worksheet: gspread.Worksheet, rows: int, cols: int):
        """
        Freeze the specified number of rows and columns
        
        Args:
            worksheet: gspread worksheet
            rows: number of rows to freeze from the top
            cols: number of cols to freeze from the bottom
        """
        
        request = {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": worksheet.id,
                    "gridProperties": {
                        "frozenRowCount": rows,
                        "frozenColumnCount": cols,
                    }
                },
                "fields": "gridProperties.frozenRowCount, gridProperties.frozenColumnCount"
            }
        }

        self.format_requests.append(request)

    def format_standings(self, worksheet: gspread.Worksheet, num_teams: int, num_cols: int):
        """
        Apply custom Google Sheet formatting rules on the Standings page.
        
        Args:
            worksheet: gspread worksheet
            num_teams: number of teams 
            num_cols: number of columns in dataframe
        """

        bold_min_cols = self._col_names_to_nums(self.standings_col_map, STANDINGS_FORMATTING['bold_min_cols'])
        color_scale_inverse_cols = self._col_names_to_nums(self.standings_col_map, STANDINGS_FORMATTING['color_scale_inverse_cols'])
        vertical_borders = self._col_names_to_nums(self.standings_col_map, STANDINGS_FORMATTING['vertical_borders'])
        col_resize_widths = { self.standings_col_map[col]: width for col, width in STANDINGS_FORMATTING['resize_cols'].items()}

        color_scale_start_col = self.standings_col_map['rank']
        bold_extreme_start_col = self.standings_col_map['wins']
        last_row = self.data_start_row + num_teams
        sos_col = self.standings_col_map['avg_opponent_rank']
        first_injury_stat_col = self.standings_col_map['games_missed_injury']
        first_avg_injury_stat_col = self.standings_col_map['avg_games_missed_injury']
        first_eff_stat_col = self.standings_col_map['player_games']
        first_avg_eff_stat_col = self.standings_col_map['avg_player_games']

        print("***NUM_COLS: ", num_cols)

        # Bold min/max columns values
        for col in range(bold_extreme_start_col, num_cols+1):
            extreme = "min" if col in bold_min_cols else "max"
            self.apply_bold_extreme(worksheet, col=col, start_row=self.data_start_row, end_row=last_row, extreme=extreme)

        # Add color scales
        for col in range(color_scale_start_col, num_cols+1):    # C -> AA
            inverse = col in color_scale_inverse_cols
            
            self.apply_color_scale(worksheet, start_row=self.data_start_row, end_row=last_row,
                               start_col=col, end_col=col+1, inverse=inverse)
            
        # Add borders
        for col in vertical_borders:
            self.apply_col_border(worksheet, col=col, start_row=1, end_row=last_row)
        self.apply_row_border(worksheet, row=last_row, start_col=1, end_col=num_cols)

        # Resize columns
        self.resize_cols(worksheet, col_resize_widths)
        self.auto_resize(worksheet, axis=0, index=1)
        self.auto_resize(worksheet, axis=0, index=2)

        # Set column headers text wrap strategy to wrap 
        self.set_text_wrap(worksheet, text_wrap=1, start_row=self.data_start_row-1, end_row=self.data_start_row, start_col=1, end_col=num_cols+1)

        # Create info header rows
        self.merge_cells(worksheet, start_row=1, end_row=2, start_col=sos_col, end_col=self.standings_col_map['cumulative_pa_rank']+1)
        self.merge_cells(worksheet, start_row=1, end_row=2, start_col=first_injury_stat_col, end_col=first_avg_injury_stat_col)
        self.merge_cells(worksheet, start_row=1, end_row=2, start_col=first_avg_injury_stat_col, end_col=first_eff_stat_col)
        self.merge_cells(worksheet, start_row=1, end_row=2, start_col=first_eff_stat_col, end_col=first_avg_eff_stat_col)
        self.merge_cells(worksheet, start_row=1, end_row=2, start_col=first_avg_eff_stat_col, end_col=num_cols+1)

        self.set_alignment(worksheet, axis=0, align=1, start_row=1, end_row=2, start_col=4, end_col=num_cols+1)
        self.set_alignment(worksheet, axis=1, align=1, start_row=1, end_row=2, start_col=1, end_col=num_cols+1)

        worksheet.update(rowcol_to_a1(1, 3), [['<- Change Sorted View on Desktop (Rank is default)']])
        worksheet.update(rowcol_to_a1(1, sos_col), [['Strength of Schedule (SoS)']])
        worksheet.update(rowcol_to_a1(1, first_injury_stat_col), [['Total Injury Stats']])
        worksheet.update(rowcol_to_a1(1, first_avg_injury_stat_col), [['Average Injury Stats Per Week']])
        worksheet.update(rowcol_to_a1(1, first_eff_stat_col), [['Lineup Efficiency']])
        worksheet.update(rowcol_to_a1(1, first_avg_eff_stat_col), [['Average Lineup Efficiency Per Week']])

        # Freze headers
        self.freeze_headers(worksheet, rows=2, cols=1)
            
    def format_weekly_rankings(self, worksheet: gspread.Worksheet, num_teams: int, num_cols: int, num_weeks: int):
        """
        Apply custom Google sheet formatting ruels on the Weekly Rankings Page

        Args:
            worksheet: gspread worksheet
            num_teams: number of rows to format (teams)
            num_cols: number of columns in dataframe
            num_weeks: number of weeks
        """

        color_scale_full_col_cols = self._col_names_to_nums(self.weekly_rankings_col_map, WEEKLY_FORMATTING['color_scale_full_col_cols'])
        color_scale_inverse_cols = self._col_names_to_nums(self.weekly_rankings_col_map, WEEKLY_FORMATTING['color_scale_inverse_cols'])
        bold_max_cols = self._col_names_to_nums(self.weekly_rankings_col_map, WEEKLY_FORMATTING['bold_max_cols'])
        bold_min_cols = self._col_names_to_nums(self.weekly_rankings_col_map, WEEKLY_FORMATTING['bold_min_cols'])
        vertical_borders = self._col_names_to_nums(self.weekly_rankings_col_map, WEEKLY_FORMATTING['vertical_borders'])
        col_resize_widths = { self.weekly_rankings_col_map[col]: width for col, width in WEEKLY_FORMATTING['resize_cols'].items()}

        color_scale_start_col = self.weekly_rankings_col_map['rank']    # E
        last_row = int(self.data_start_row + (num_weeks * num_teams))
        sos_col = self.weekly_rankings_col_map['cumulative_pa_rank']
        first_injury_stat_col = self.weekly_rankings_col_map['games_missed_injury']
        first_cum_injury_stat_col = self.weekly_rankings_col_map['cumulative_games_missed_injury']
        first_eff_stat_col = self.weekly_rankings_col_map['player_games']

        print("***NUM_COLS: ", num_cols)

        # Highlight winner rows
        self.apply_highlight_win_rows(worksheet, num_cols, end_row=last_row)

        # Bold min/max columns values
        for col in bold_max_cols:
            self.apply_bold_extreme(worksheet, col)
        for col in bold_min_cols:
            self.apply_bold_extreme(worksheet, col, extreme="min")

        # Color scales for cols divided by weeks
        for week in range(num_weeks):   # E -> AD
            week_start_row = self.data_start_row + (week * num_teams)

            for col in range(color_scale_start_col, num_cols+1):
                inverse = col in color_scale_inverse_cols
                start_row = self.data_start_row if col in color_scale_full_col_cols else week_start_row
                end_row = last_row if col in color_scale_full_col_cols else week_start_row + num_teams

                self.apply_color_scale(worksheet, start_row=start_row, end_row=end_row,
                                       start_col=col, end_col=col+1, inverse=inverse)
            
        # Add borders
        for col in vertical_borders:
            self.apply_col_border(worksheet, col=col, start_row=1, end_row=last_row)
        self.apply_row_border(worksheet, row=last_row, start_col=1, end_col=num_cols)

        # Resize columns
        self.resize_cols(worksheet, col_resize_widths)
        self.auto_resize(worksheet, axis=0, index=1)    # First row
        self.auto_resize(worksheet, axis=0, index=2)    # Second row

        # Set column headers text wrap strategy to wrap 
        self.set_text_wrap(worksheet, text_wrap=1, start_row=self.data_start_row-1, end_row=self.data_start_row, start_col=1, end_col=num_cols+1)

        # Create info header rows
        self.merge_cells(worksheet, start_row=1, end_row=2, start_col=first_injury_stat_col, end_col=first_cum_injury_stat_col)
        self.merge_cells(worksheet, start_row=1, end_row=2, start_col=first_cum_injury_stat_col, end_col=first_eff_stat_col)
        self.merge_cells(worksheet, start_row=1, end_row=2, start_col=first_eff_stat_col, end_col=num_cols+1)

        self.set_alignment(worksheet, axis=0, align=2, start_row=1, end_row=2, start_col=sos_col, end_col=sos_col+1)
        self.set_alignment(worksheet, axis=0, align=1, start_row=1, end_row=2, start_col=first_injury_stat_col, end_col=num_cols+1)
        self.set_alignment(worksheet, axis=1, align=1, start_row=1, end_row=2, start_col=1, end_col=num_cols+1)
        
        worksheet.update(rowcol_to_a1(1, 3), [['<- Change Grouped View on Desktop (Week is default)']])
        worksheet.update(rowcol_to_a1(1, sos_col), [['Strength of Schedule (SoS)']])
        worksheet.update(rowcol_to_a1(1, first_injury_stat_col), [['Weekly Total Injury Stats']])
        worksheet.update(rowcol_to_a1(1, first_cum_injury_stat_col), [['Cumulative Injury Stats']])
        worksheet.update(rowcol_to_a1(1, first_eff_stat_col), [['Weekly Lineup Efficiency']])

        # Freze headers
        self.freeze_headers(worksheet, rows=2, cols=2)


class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass
