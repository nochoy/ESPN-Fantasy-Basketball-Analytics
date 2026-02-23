"""
Fantasy Basketball Calculations Module
Computes all advanced statistics and metrics
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from collections import defaultdict


class FantasyCalculator:
    """Calculator for fantasy basketball analytics"""
    
    def __init__(self, matchup_summaries: List[Dict], matchups: List[Dict], teams: List[Dict], player_avg_points: Dict[int, float]):
        """
        Initialize calculator with league data
        
        Args:
            matchups: List of all matchup data from ESPN
            teams: List of team information
            player_avg_points: Dictionary mapping player ids to fantasy point average
        """
        self.matchup_summaries = matchup_summaries
        self.matchups = matchups
        self.teams = {t['id']: t for t in teams}
        self.team_ids = list(self.teams.keys())
        self.player_avg_points = player_avg_points
        
        self.max_week = max(m['week'] for m in matchup_summaries) if matchup_summaries else 0
        
        self._build_dataframes()
    
    def _build_dataframes(self):
        """Convert matchup data to pandas DataFrames"""
        # Create weekly scores dataframe
        weekly_data = []
        
        for matchup in self.matchup_summaries:
            week = matchup['week']
            
            # Home team
            weekly_data.append({
                'week': week,
                'team_id': matchup['home_team']['id'],
                'team_name': matchup['home_team']['name'],
                'pf': matchup['home_team']['score'],
                'pa': matchup['away_team']['score'],
                'opponent_id': matchup['away_team']['id'],
                'opponent_name': matchup['away_team']['name'],
                'is_home': True
            })
            
            # Away team (if not BYE)
            if matchup['away_team']['id'] is not None:
                weekly_data.append({
                    'week': week,
                    'team_id': matchup['away_team']['id'],
                    'team_name': matchup['away_team']['name'],
                    'pf': matchup['away_team']['score'],
                    'pa': matchup['home_team']['score'],
                    'opponent_id': matchup['home_team']['id'],
                    'opponent_name': matchup['home_team']['name'],
                    'is_home': False
                })
        
        self.weekly_df = pd.DataFrame(weekly_data)
        
        # Sort by week and team
        self.weekly_df = self.weekly_df.sort_values(['week', 'team_id'])
        print("**************self.weekly_df dataframe: \n", self.weekly_df.head(12))
        print(len(self.weekly_df[self.weekly_df['is_home'] == False]))
        print(len(self.weekly_df[self.weekly_df['is_home'] == True]))
    
    def calculate_weekly_pf_pa_rankings(self) -> pd.DataFrame:
        """
        Calculate weekly PF and PA rankings
        
        Returns:
            DataFrame with weekly rankings for each team
        """
        df = self.weekly_df.copy()
        
        # Calculate PF rank for each week (1 = highest scorer)
        df['pf_rank'] = df.groupby('week')['pf'].rank(ascending=False, method='min')
        
        # Calculate PA rank for each week (1 = highest points against)
        df['pa_rank'] = df.groupby('week')['pa'].rank(ascending=False, method='min')

        df['differential'] = df['pf'] - df['pa']
        
        return df[['week', 'team_id', 'team_name', 'pf', 'pa', 'pf_rank', 'pa_rank', 'opponent_id', 'differential']]
    
    def calculate_cumulative_stats(self) -> pd.DataFrame:
        """
        Calculate cumulative PF, PA, and differentials
        
        Returns:
            DataFrame with cumulative stats per team
        """
        df = self.weekly_df.copy()
        
        # Sort by week for cumulative calculation
        df = df.sort_values(['team_id', 'week'])

        # Calculate PF and PA rank for each week (helpers)
        df['pf_rank'] = df.groupby('week')['pf'].rank(ascending=False, method='min')
        df['pa_rank'] = df.groupby('week')['pa'].rank(ascending=False, method='min')
        
        # Calculate cumulative stats
        df['cumulative_pf'] = df.groupby('team_id')['pf'].cumsum()
        df['cumulative_pa'] = df.groupby('team_id')['pa'].cumsum()
        df['cumulative_differential'] = df['cumulative_pf'] - df['cumulative_pa']

        # Calculate cumulative wins/losses per week
        df['win'] = (df['pf'] > df['pa']).astype(int)
        df['loss'] = (df['pf'] < df['pa']).astype(int)
        df['wins'] = df.groupby('team_id')['win'].cumsum()
        df['losses'] = df.groupby('team_id')['loss'].cumsum()
        df['games_played'] = df['wins'] + df['losses']
        df['win_pct'] = (df['wins'] / df['games_played']).round(3)
        
        # Calculate cumulative rankings by week
        # Rank by cumulative PF (descending) - rank 1 = most points scored
        df['cumulative_pf_rank'] = round(df.groupby('week')['pf_rank'].expanding().mean().reset_index(0, drop=True), 2)
        
        # Rank by cumulative PA (ascending) - rank 1 = most points against
        df['cumulative_pa_rank'] = round(df.groupby('team_id')['pa_rank'].expanding().mean().reset_index(0, drop=True), 2)
        
        # Calculate overall rank by wins, then cumulative PF
        df['rank'] = (df.sort_values(['week', 'win_pct', 'cumulative_pf'], ascending=[True, False, False]).groupby('week').cumcount() + 1)

        df = df.drop(['pf_rank', 'pa_rank'], axis=1)
        
        return df[['week', 'rank', 'team_id', 'team_name', 'wins', 'losses', 'win_pct', 'cumulative_pf_rank', 'cumulative_pa_rank', 'cumulative_pf', 'cumulative_pa', 'cumulative_differential']]
    
    def calculate_toughest_opponent_rank(self) -> pd.DataFrame:
        """
        Calculate toughest opponent rank based on weekly PF ranks
        - For each matchup, get opponent's PF rank that week
        - Average across all weeks for season toughness
        
        Returns:
            DataFrame with opponent toughness metrics
        """
        df = self.calculate_weekly_pf_pa_rankings()
        
        # Create opponent's PF rank lookup
        opponent_ranks = df[['week', 'team_id', 'pf_rank']].rename(
            columns={'team_id': 'opponent_id', 'pf_rank': 'opponent_pf_rank'}
        )
        # print("ooponent_ranks: \n", opponent_ranks.to_string())
        
        # Merge to get opponent's rank for each matchup
        df_with_opp = df.merge(
            opponent_ranks,
            left_on=['week', 'opponent_id'],
            right_on=['week', 'opponent_id'],
            how='left'
        )
        
        # Group by team and week to get opponent rank
        result = df_with_opp.groupby(['week', 'team_id', 'team_name']).agg({
            'opponent_pf_rank': 'first',
            'pf': 'first',
            'pa': 'first'
        }).reset_index()
        
        # Calculate cumulative average opponent rank (lower is tougher)
        result = result.sort_values(['team_id', 'week'])
        result['cumulative_avg_opp_rank'] = round(result.groupby('team_id')['opponent_pf_rank'].expanding().mean().reset_index(0, drop=True), 2)
        
        return result[['week', 'team_id', 'team_name', 'opponent_pf_rank', 'cumulative_avg_opp_rank', 'pf', 'pa']]
    
    def calculate_injury_stats(self) -> pd.DataFrame:
        """
        Calculate injury-related statistics
        - Games missed due to injury (player on roster but DTD/OUT/INJ)
        - Games missed from IR slot
        - Lost fantasy points from injured players
        
        Returns:
            DataFrame with injury statistics
        """
        injury_data = []

        for matchup in self.matchups:
            week = matchup['week']
            
            for side in ['home_team', 'away_team']:
                team_data = matchup[side]
                lineup = team_data['lineup']
                team_id = team_data['id']
                team_name = team_data['name']
                # print("week: ", week, " - side: ", side, " - team_name: ", team_name)

                games_missed_injury = 0
                games_missed_ir = 0
                lost_points_injury = 0
                lost_points_ir = 0

                for player in lineup:
                    if player['injured_game']:
                        if player['slot_position'] == 'IR':
                            games_missed_ir += 1
                            lost_points_ir += self.player_avg_points[player['player_id']]
                        else:   # Missed game, but not on IR
                            games_missed_injury += 1
                            lost_points_injury += self.player_avg_points[player['player_id']]

                injury_data.append({
                    'week': week,
                    'team_id': team_id,
                    'team_name': team_name,
                    'games_missed_injury': games_missed_injury,
                    'games_missed_ir': games_missed_ir,
                    'total_games_missed': games_missed_injury + games_missed_ir,
                    'lost_points_injury': round(lost_points_injury, 2),
                    'lost_points_ir': round(lost_points_ir, 2),
                    'total_lost_points': round(lost_points_injury + lost_points_ir, 2),
                })

        df = pd.DataFrame(injury_data)
        # print("RAW INJURY STATS: \n", df.head(12).to_string(index=False))

        df = df.groupby(['week', 'team_id', 'team_name']).sum().reset_index()
        # print("GROUPED INJKURY STATS: \n", df.head(24).to_string(index=False))
        
        # Calculate cumulative stats - broken down by injury vs IR
        if not df.empty:
            df = df.sort_values(['team_id', 'week'])
            
            # Cumulative columns broken down
            df['cumulative_games_missed_injury'] = df.groupby('team_id')['games_missed_injury'].cumsum()
            df['cumulative_games_missed_ir'] = df.groupby('team_id')['games_missed_ir'].cumsum()
            df['cumulative_total_games_missed'] = df.groupby('team_id')['total_games_missed'].cumsum()
            
            df['cumulative_lost_points_injury'] = df.groupby('team_id')['lost_points_injury'].cumsum()
            df['cumulative_lost_points_ir'] = df.groupby('team_id')['lost_points_ir'].cumsum()
            df['cumulative_total_lost_points'] = df.groupby('team_id')['total_lost_points'].cumsum()
            
            # Average columns (cumulative / weeks played)
            df['avg_games_missed_injury'] = (df['cumulative_games_missed_injury'] / df['week']).round(2)
            df['avg_games_missed_ir'] = (df['cumulative_games_missed_ir'] / df['week']).round(2)
            df['avg_total_games_missed'] = (df['cumulative_total_games_missed'] / df['week']).round(2)
            
            df['avg_lost_points_injury'] = (df['cumulative_lost_points_injury'] / df['week']).round(2)
            df['avg_lost_points_ir'] = (df['cumulative_lost_points_ir'] / df['week']).round(2)
            df['avg_total_lost_points'] = (df['cumulative_total_lost_points'] / df['week']).round(2)
        
        # print("RAW INJURY STATS AFTER CUMULATIVE + AVERAGE CALCULATION:\n", df.head(24).to_string(index=False))
        
        return df
    
    def calculate_luck_factor(self) -> pd.DataFrame:
        """
        Calculate luck factor - compare actual wins to expected wins
        Expected wins = probability of beating each other team that week
        
        Returns:
            DataFrame with luck metrics
        """
        df = self.weekly_df.copy()
        luck_data = []
        
        for week in range(1, self.max_week + 1):
            week_df = df[df['week'] == week]
            
            for _, team_row in week_df.iterrows():
                team_id = team_row['team_id']
                team_pf = team_row['pf']
                opponent_id = team_row['opponent_id']
                opponent_pf = team_row['pa']
                
                # Count how many teams this team would have beaten
                all_scores = week_df['pf'].values
                teams_beaten = sum(1 for score in all_scores if team_pf > score)
                teams_tied = sum(1 for score in all_scores if team_pf == score) - 1  # Exclude self
                
                # Expected wins = teams beaten / (total teams - 1)
                total_teams = len(self.team_ids)
                expected_wins = (teams_beaten + 0.5 * teams_tied) / (total_teams - 1)
                
                # Actual result
                actual_win = 1 if team_pf > opponent_pf else (0.5 if team_pf == opponent_pf else 0)
                
                luck_data.append({
                    'week': week,
                    'team_id': team_id,
                    'team_name': team_row['team_name'],
                    'pf': team_pf,
                    'teams_beaten': teams_beaten,
                    'expected_wins': round(expected_wins, 3),
                    'actual_result': actual_win,
                    'luck_factor': round(actual_win - expected_wins, 3)
                })
        
        luck_df = pd.DataFrame(luck_data)
        
        # Calculate cumulative luck
        if not luck_df.empty:
            luck_df = luck_df.sort_values(['team_id', 'week'])
            luck_df['cumulative_expected_wins'] = luck_df.groupby('team_id')['expected_wins'].cumsum()
            luck_df['cumulative_actual_wins'] = luck_df.groupby('team_id')['actual_result'].cumsum()
            luck_df['cumulative_luck'] = luck_df['cumulative_actual_wins'] - luck_df['cumulative_expected_wins']
        
        return luck_df
    
    def calculate_consistency(self) -> pd.DataFrame:
        """
        Calculate consistency score (lower std dev = more consistent)
        
        Returns:
            DataFrame with consistency metrics
        """
        df = self.weekly_df.copy()
        
        consistency = df.groupby(['team_id', 'team_name']).agg({
            'pf': ['mean', 'std', 'min', 'max', 'count']
        }).reset_index()
        
        consistency.columns = ['team_id', 'team_name', 'avg_pf', 'std_pf', 'min_pf', 'max_pf', 'games_played']
        
        # Calculate coefficient of variation (std/mean) - lower is more consistent
        consistency['consistency_score'] = consistency['std_pf'] / consistency['avg_pf']
        consistency['range'] = consistency['max_pf'] - consistency['min_pf']
        
        return consistency.round(2)
    
    def get_standings(self) -> pd.DataFrame:
        """
        Get current standings with calculated stats
        
        Returns:
            DataFrame with full standings
        """
        standings = []
        
        for team_id, team in self.teams.items():
            # if team_id == 1: print("TEAM DATA: ", team)
            team_weeks = self.weekly_df[self.weekly_df['team_id'] == team_id]
            
            wins = sum(1 for _, row in team_weeks.iterrows() if row['pf'] > row['pa'])
            losses = sum(1 for _, row in team_weeks.iterrows() if row['pf'] < row['pa'])
            ties = sum(1 for _, row in team_weeks.iterrows() if row['pf'] == row['pa'])
            
            standings.append({
                'team_id': team_id,
                'team_name': team['name'],
                'wins': wins,
                'losses': losses,
                'ties': ties,
                'win_pct': round(wins / (wins + losses + ties), 3) if (wins + losses + ties) > 0 else 0,
                'total_pf': round(team_weeks['pf'].sum(), 2),
                'total_pa': round(team_weeks['pa'].sum(), 2),
                'avg_pf': round(team_weeks['pf'].mean(), 2),
                'avg_pa': round(team_weeks['pa'].mean(), 2),
                'differential': round(team_weeks['pf'].sum() - team_weeks['pa'].sum(), 2),
            })
        
        df = pd.DataFrame(standings)
        df = df.sort_values(['wins', 'total_pf'], ascending=[False, False])
        df['rank'] = range(1, len(df) + 1)
        df['avg_differential'] = round(df['differential'] / self.max_week, 2)
        
        return df
    
    def generate_all_stats(self) -> Dict[str, pd.DataFrame]:
        """
        Generate all statistics at once
        
        Returns:
            Dictionary of DataFrames with all calculated stats
        """
        print("Calculating all statistics...")
        
        stats = {
            'standings': self.get_standings(),
            'weekly_rankings': self.calculate_weekly_pf_pa_rankings(),
            'cumulative_stats': self.calculate_cumulative_stats(),
            'toughest_opponents': self.calculate_toughest_opponent_rank(),
            'injury_stats': self.calculate_injury_stats(),
            # 'luck_factor': self.calculate_luck_factor(),
            # 'consistency': self.calculate_consistency()
        }
        
        print("✓ All statistics calculated")
        return stats
