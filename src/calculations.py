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
        self.weekly_df = self.weekly_df.sort_values(['week', 'team_id'])
        # print("**************self.weekly_df dataframe: \n", self.weekly_df.head(12))
    
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
        
        return df[['week', 'team_id', 'team_name', 'pf', 'pa', 'pf_rank', 'pa_rank', 'opponent_id', 'opponent_name', 'differential']]
    
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
        df['cumulative_pf_rank'] = round(df.groupby('team_id')['pf_rank'].expanding().mean().reset_index(0, drop=True), 2)
        
        # Rank by cumulative PA (ascending) - rank 1 = most points against
        df['cumulative_pa_rank'] = round(df.groupby('team_id')['pa_rank'].expanding().mean().reset_index(0, drop=True), 2)
        
        # Calculate overall rank by wins, then cumulative PF
        df['rank'] = (df.sort_values(['week', 'win_pct', 'cumulative_pf'], ascending=[True, False, False]).groupby('week').cumcount() + 1)

        df = df.drop(['pf_rank', 'pa_rank'], axis=1)
        
        return df[['week', 'rank', 'team_id', 'team_name', 'wins', 'losses', 'win_pct', 'cumulative_pf_rank', 'cumulative_pa_rank', 'cumulative_pf', 'cumulative_pa', 'cumulative_differential']]
    
    def calculate_injury_stats(self) -> pd.DataFrame:
        """
        Calculate injury-related statistics
        - Games missed from starters or bench
        - Games missed from IR slot
        - Lost fantasy points from injured players
        
        Returns:
            DataFrame with injury statistics
        """
        injury_data = []
        bronny_count = 0

        for matchup in self.matchups:
            week = matchup['week']
            
            for side in ['home_team', 'away_team']:
                team_data = matchup[side]
                lineup = team_data['lineup']
                team_id = team_data['id']
                team_name = team_data['name']
                games_missed_injury = 0
                games_missed_ir = 0
                lost_points_injury = 0
                lost_points_ir = 0

                for player in lineup:
                    if player['injured_game']:
                        if player['name'] == "Bronny James":
                            bronny_count += 1
                            continue
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

        df = pd.DataFrame(injury_data).groupby(['week', 'team_id', 'team_name']).sum().reset_index()
        print("*****BRONY INJURED GAMES COUNT: ", bronny_count)
        
        # Calculate cumulative stats - broken down by injury (start/bench) vs IR
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
                
        return df
    
    def calculate_lineup_efficiency(self) -> pd.DataFrame:
        """
        Calculate number of games (starter, bench, IR) and points lost due to players left on bench/IR.
        Only counts if fewer than 10 active starters 
        """

        efficiency_data = []

        for matchup in self.matchups:
            week = matchup['week']

            for side in ['home_team', 'away_team']:
                team_data = matchup[side]
                lineup = team_data['lineup']
                team_id = team_data['id']
                team_name = team_data['name']
                starter_games = 0
                bench_points = []
                ir_points = []

                for player in lineup:
                    if player['slot_position'] == 'BE' and player['points'] > 0:
                        bench_points.append(player['points'])
                    elif player['slot_position'] == 'IR' and player['points'] > 0:
                        ir_points.append(player['points'])
                    elif player['slot_position'] not in ['BE', 'IR'] and player['points'] > 0:   # starter
                        starter_games += 1

                remaining_pg = 10 - starter_games
                bench_points.sort(reverse=True)
                ir_points.sort(reverse=True)

                bench_games = len(bench_points[:remaining_pg])
                bench_points_lost = sum(bench_points[:remaining_pg])
                
                ir_games = len(ir_points[:remaining_pg])
                ir_points_lost = sum(ir_points[:remaining_pg])

                efficiency_data.append({
                    'week': week,
                    'team_id': team_id,
                    'team_name': team_name,
                    'player_games': starter_games,
                    'bench_games': bench_games,
                    'ir_games': ir_games,
                    'total_missed_games': bench_games + ir_games,
                    'bench_points_lost': bench_points_lost,
                    'ir_points_lost': ir_points_lost,
                    'total_points_lost': bench_points_lost + ir_points_lost
                })

        # Weekly totals
        df = pd.DataFrame(efficiency_data).groupby(['week', 'team_id', 'team_name']).sum().reset_index()

        return df

    def calculate_lineup_efficiency_standings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates season totals for total number of games (starter, BE, IR) and 
        points lost due players being left on the bench and IR. 
        """

        if 'player_games' not in df.columns:
            return

        efficiency_standings = df.groupby(['team_id', 'team_name']).sum().reset_index()

        efficiency_standings['avg_player_games'] = round(efficiency_standings['player_games'] / self.max_week, 2)
        efficiency_standings['avg_bench_games'] = round(efficiency_standings['bench_games'] / self.max_week, 2)
        efficiency_standings['avg_ir_games'] = round(efficiency_standings['ir_games'] / self.max_week, 2)
        efficiency_standings['avg_total_missed_games'] = round(efficiency_standings['total_missed_games'] / self.max_week, 2)
        efficiency_standings['avg_bench_points_lost'] = round(efficiency_standings['bench_points_lost'] / self.max_week, 2)
        efficiency_standings['avg_ir_points_lost'] = round(efficiency_standings['ir_points_lost'] / self.max_week, 2)
        efficiency_standings['avg_total_points_lost'] = round(efficiency_standings['total_points_lost'] / self.max_week, 2)

        return efficiency_standings.drop('week').sort_values(['total_points_lost'], ascending=False)


    def get_standings(self) -> pd.DataFrame:
        """
        Get current standings with calculated stats
        
        Returns:
            DataFrame with full standings
        """
        standings = []
        
        for team_id, team in self.teams.items():
            team_matchups = self.weekly_df[self.weekly_df['team_id'] == team_id]
            
            wins = sum(1 for _, row in team_matchups.iterrows() if row['pf'] > row['pa'])
            losses = sum(1 for _, row in team_matchups.iterrows() if row['pf'] < row['pa'])
            ties = sum(1 for _, row in team_matchups.iterrows() if row['pf'] == row['pa'])
            
            standings.append({
                'team_id': team_id,
                'team_name': team['name'],
                'wins': wins,
                'losses': losses,
                'ties': ties,
                'win_pct': round(wins / (wins + losses + ties), 3) if (wins + losses + ties) > 0 else 0,
                'total_pf': round(team_matchups['pf'].sum(), 2),
                'total_pa': round(team_matchups['pa'].sum(), 2),
                'avg_pf': round(team_matchups['pf'].mean(), 2),
                'avg_pa': round(team_matchups['pa'].mean(), 2),
                'differential': round(team_matchups['pf'].sum() - team_matchups['pa'].sum(), 2),
            })
        
        df = pd.DataFrame(standings)
        df = df.sort_values(['wins', 'total_pf'], ascending=[False, False])

        # Determine rank based on win count, with PF as tie breaker
        df['rank'] = range(1, len(df) + 1)
        df['avg_differential'] = round(df['differential'] / self.max_week, 2)

        # Calculate average opponent rank, where rank is based on final standings
        final_ranks = df.set_index('team_id')['rank'].to_dict()
        avg_opponent_ranks = []
        
        for _, row in df.iterrows():
            team_id = row['team_id']
            team_matchups = self.weekly_df[self.weekly_df['team_id'] == team_id]
            opponent_ids = [oid for oid in team_matchups['opponent_id'] if oid is not None]
            opponent_ranks = [final_ranks.get(oid, 0) for oid in opponent_ids]
            avg_rank = sum(opponent_ranks) / len(opponent_ranks) if opponent_ranks else 0
            avg_opponent_ranks.append(round(avg_rank, 2))

        df['avg_opponent_rank'] = avg_opponent_ranks

        return df
    
    def generate_all_stats(self) -> Dict[str, pd.DataFrame]:
        """
        Generate all statistics at once
        
        Returns:
            Dictionary of DataFrames with all calculated stats
        """
        print("Calculating all statistics...")

        standings = self.get_standings()
        cumulative_stats = self.calculate_cumulative_stats()
        toughness_summary = cumulative_stats.groupby(['team_name', 'team_id'])['cumulative_pa_rank'].last().sort_values().reset_index()
        efficiency_stats = self.calculate_lineup_efficiency()
        efficiency_summary = self.calculate_lineup_efficiency_standings(efficiency_stats)

        # dataframe with team_id + team_name + avg_opponent_rank + cumulative_pa_rank to differentiate SoS stats
        toughness_summary = toughness_summary.merge(
            standings[['team_id', 'team_name', 'avg_opponent_rank', 'rank']], 
            on=['team_id', 'team_name'], 
            how='left'
        )
        
        toughness_col_order = ['team_id', 'team_name', 'rank', 'avg_opponent_rank', 'cumulative_pa_rank']
        
        stats = {
            'standings': standings,
            'weekly_rankings': self.calculate_weekly_pf_pa_rankings(),
            'cumulative_stats': cumulative_stats,
            'toughness_summary': toughness_summary[toughness_col_order],
            'injury_stats': self.calculate_injury_stats(),
            'efficiency_stats': efficiency_stats,
            'efficiency_summary': efficiency_summary,
        }
        
        print("✓ All statistics calculated")
        return stats
