"""
Google Sheets Export Module
Handles exporting fantasy data to Google Sheets
"""

import os
import pandas as pd
from datetime import date
from typing import Dict, Optional
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
        self.credentials_path = credentials_path or os.getenv('GOOGLE_CREDENTIALS_PATH', './config/google-credentials.json')
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
        full_standings_df = pd.merge(standings_and_injury_df, toughness_standings, on=['team_id', 'team_name'], how='outer')

        # Reorder columns
        full_standings_df_col_order = [
            'team_name', 'team_id', 'rank', 'wins', 'losses', 'ties', 'win_pct', 
            'total_pf', 'total_pa', 'differential', 'avg_opponent_rank', 'cumulative_pa_rank', 
            'avg_pf', 'avg_pa', 'avg_differential',
            'games_missed_injury', 'games_missed_ir', 'total_games_missed', 
            'lost_points_injury', 'lost_points_ir', 'total_lost_points', 
            'avg_games_missed_injury', 'avg_games_missed_ir', 'avg_total_games_missed', 
            'avg_lost_points_injury', 'avg_lost_points_ir', 'avg_total_lost_points'
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
        full_weekly_rankings_df = pd.merge(weekly_and_cumulative_df, injury_weekly, on=['week', 'team_id', 'team_name'], how='outer')

        # Reorder columns
        master_weekly_col_order = [
            'week', 'team_name', 'team_id', 'opponent_name', 'rank', 'wins', 'losses', 'win_pct', 
            'pf', 'pa', 'differential', 'pf_rank', 'pa_rank', 
            'cumulative_pf', 'cumulative_pa', 'cumulative_differential', 'cumulative_pf_rank', 'cumulative_pa_rank', 
            'games_missed_injury', 'games_missed_ir', 'total_games_missed', 
            'lost_points_injury', 'lost_points_ir', 'total_lost_points', 
            'cumulative_games_missed_injury', 'cumulative_games_missed_ir', 'cumulative_total_games_missed', 
            'cumulative_lost_points_injury', 'cumulative_lost_points_ir', 'cumulative_total_lost_points'
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
        standings_ws = self.create_worksheet('Standings', len(full_standings_df)+2, len(full_standings_df.columns))
        self.write_dataframe(standings_ws, full_standings_df, start_cell='A2')
        self.format_standings(standings_ws, len(full_standings_df), len(full_standings_df.columns))

        print("  ✓ Exported: Standings")
        
        # Compile Weekly Rankings page stats, export to Google sheet, and apply formatting
        full_weekly_rankings_df = self._compile_weekly_rankings_df()
        ws_weekly = self.create_worksheet('Weekly Rankings', len(full_weekly_rankings_df)+2, len(full_weekly_rankings_df.columns))
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

    def _build_col_map(self, df: pd.DataFrame) -> dict[str, int]:
        """
        Create mapping of column_name -> 1-based column index (Google Sheets style)
        """

        return {col: i+1 for i, col in enumerate(df.columns)}
    
    def _col_names_to_nums(self, col_map: Dict[str, int], col_names: list[str]) -> list[int]:
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
                          min_color: Optional[dict] = None, mid_color: Optional[dict] = None, 
                          max_color: Optional[dict] = None, inverse: bool = False):
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
                        "endRowIndex": end_row,
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
                        "endRowIndex": end_row,
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

    def format_standings(self, worksheet: gspread.Worksheet, num_teams, num_cols):
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

        color_scale_start_col = self.standings_col_map['rank']  # C
        bold_extreme_start_col = self.standings_col_map['wins'] # D
        last_row = self.data_start_row + num_teams

        # Bold min/max columns values
        for col in range(bold_extreme_start_col, num_cols+1):
            extreme = "min" if col in bold_min_cols else "max"
            self.apply_bold_extreme(worksheet, col, extreme=extreme)

        # Add color scales
        for col in range(color_scale_start_col, num_cols+1):    # C -> AA
            inverse = col in color_scale_inverse_cols
            
            self.apply_color_scale(worksheet, start_row=self.data_start_row, end_row=last_row,
                               start_col=col, end_col=col+1, inverse=inverse)
            
        # Add borders
        for col in vertical_borders:
            self.apply_col_border(worksheet, col, 1, num_teams + self.data_start_row)
        self.apply_row_border(worksheet, last_row, 1, num_cols)
            
    def format_weekly_rankings(self, worksheet: gspread.Worksheet, num_teams, num_cols, num_weeks):
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

        color_scale_start_col = self.weekly_rankings_col_map['rank']    # E
        last_row = int(self.data_start_row + (num_weeks * num_teams))

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
            self.apply_col_border(worksheet, col, 1, last_row)
        self.apply_row_border(worksheet, last_row, 1, num_cols)

class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass
