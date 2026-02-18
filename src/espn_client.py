"""
ESPN Fantasy Basketball API Client
Handles connection and data retrieval from ESPN
"""

import os
from typing import Optional, List, Dict, Any
from espn_api.basketball import League
from dotenv import load_dotenv

load_dotenv()


class ESPNClient:
    """Client for interacting with ESPN Fantasy Basketball API"""
    
    def __init__(self, league_id: Optional[int] = None, year: Optional[int] = None):
        """
        Initialize ESPN client
        
        Args:
            league_id: ESPN league ID (from URL)
            year: Season year
        """
        self.league_id = league_id or int(os.getenv('ESPN_LEAGUE_ID', 0))
        self.year = year or int(os.getenv('ESPN_YEAR', 2026))
        self.espn_s2 = os.getenv('ESPN_S2')
        self.swid = os.getenv('ESPN_SWID')
        
        if not self.league_id:
            raise ValueError("League ID is required. Set ESPN_LEAGUE_ID in .env file")
        
        self.league: Optional[League] = None
        self._connect()
    
    def _connect(self):
        """Establish connection to ESPN league"""
        try:
            if self.espn_s2 and self.swid:
                # Private league authentication
                self.league = League(
                    league_id=self.league_id,
                    year=self.year,
                    espn_s2=self.espn_s2,
                    swid=self.swid
                )
                print(f"✓ Connected to private league {self.league_id}")
            else:
                # Public league (no auth needed)
                self.league = League(
                    league_id=self.league_id,
                    year=self.year
                )
                print(f"✓ Connected to public league {self.league_id}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to ESPN league: {e}")
    
    def get_league_info(self) -> Dict[str, Any]:
        """Get basic league information"""
        # Use matchup period instead of current_week (which can be buggy during playoffs)
        current_matchup = getattr(self.league, 'currentMatchupPeriod', 
                                  getattr(self.league, 'current_week', 1))
        
        reg_season_weeks = self.league.settings.reg_season_count
        total_weeks = len(self.league.settings.matchup_periods)
        
        # Determine season phase
        if current_matchup <= reg_season_weeks:
            season_phase = "regular_season"
        else:
            season_phase = "playoffs"
        
        return {
            'name': self.league.settings.name,
            'season': self.league.year,
            'teams_count': len(self.league.teams),
            'current_week': current_matchup,
            'reg_season_weeks': reg_season_weeks,
            'playoff_rounds': total_weeks - reg_season_weeks,
            'total_weeks': total_weeks,
            'season_phase': season_phase,
            'scoring_type': self.league.settings.scoring_type,
        }
    
    def get_teams(self) -> List[Dict[str, Any]]:
        """Get all teams in the league"""
        teams = []
        for team in self.league.teams:
            teams.append({
                'id': team.team_id,
                'name': team.team_name,
                'owner': getattr(team, 'owners', ['Unknown'])[0] if hasattr(team, 'owners') else 'Unknown',
                'wins': team.wins,
                'losses': team.losses,
                'ties': getattr(team, 'ties', 0),
                'points_for': team.points_for,
                'points_against': team.points_against,
                'streak': getattr(team, 'streak', ''),
                'standing': team.standing,
                'final_standing': team.final_standing,
            })
        return teams
    
    def get_box_scores(self, week: int, scoring_period: int = None, matchup_total: bool = True) -> List[Dict[str, Any]]:
        """
        Get all box scores for a specific week
        
        Args:
            week: Week number
            scoring_period: Specific scoring period (day) within the week
            matchup_total: If True, returns aggregated matchup totals; if False, returns individual scoring period
            
        Returns:
            List of matchup data
        """
        try:
            box_scores = self.league.box_scores(matchup_period=week, scoring_period=scoring_period, matchup_total=matchup_total)
            matchups = []

            # count = 0
            for matchup in box_scores:
                # if count == 0: print("***WEEK: ", week, " - MATCHUP SCORING PERIOD: ", matchup.scoring_period)
                # count+= 1                ]
                matchups.append({
                    'week': week,
                    'scoring_period': matchup.scoring_period,
                    'home_team': {
                        'id': matchup.home_team.team_id,
                        'name': matchup.home_team.team_name,
                        'score': matchup.home_score,
                        'lineup': self._extract_lineup(matchup.home_lineup)
                    },
                    'away_team': {
                        'id': matchup.away_team.team_id if matchup.away_team else None,
                        'name': matchup.away_team.team_name if matchup.away_team else 'BYE',
                        'score': matchup.away_score,
                        'lineup': self._extract_lineup(matchup.away_lineup) if matchup.away_lineup else []
                    }
                })
                # if count == 0: print('FIRST MATCHUP******: \n', matchups[0])
                # count += 1

            return matchups
        except Exception as e:
            print(f"Error fetching box scores for week {week}, scoring_period {scoring_period}: {e}")
            return []
    
    def _extract_lineup(self, lineup) -> List[Dict[str, Any]]:
        """Extract player data from lineup"""

        try:

            players = []
            count = 0

            for player in lineup:

                # if count == 0: print('player: ', dir(player))
                # else: exit()
                # count+= 1

                players.append({
                    'name': player.name,
                    'player_id': player.playerId,
                    'position': player.position,
                    'slot_position': player.slot_position,
                    'points': player.points,
                    # 'projected_points': getattr(player, 'projected_points', 0),
                    'injury_status': getattr(player, 'injuryStatus', 'UNKNOWN'),
                    # 'injured': player.injured,
                    # 'pro_opponent': player.pro_opponent,
                    'injured_game': player.pro_opponent != 'None' and player.points == 0 and player.stats != {},
                    # 'stats': player.stats
                    # 'avg_points': avg_points[player.playerId] if include_avg_points else -1
                })
                # if player.pro_opponent != 'None' and player.points == 0 and player.stats != {}:
                #     print(player.name)
                #     count+= 1
            # print("MISSED GAMES: ", count)
            return players
        except Exception as e:
            print(f"Error extracting lineup: {e}")
            return []
    
    def get_all_matchup_summaries(self, start_week: int = 1, end_week: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get matchup summaries for multiple weeks (aggregated totals)
        
        Args:
            start_week: Starting week
            end_week: Ending week (defaults to current week)
            
        Returns:
            List of all matchups with aggregated totals
        """
        try:

            if end_week is None:
                end_week = getattr(self.league, 'current_week', 1)
            
            all_matchups = []
            print(f"Fetching matchup summaries for weeks {start_week}-{end_week}...")
            
            for week in range(start_week, end_week + 1):
                matchups = self.get_box_scores(week, matchup_total=True)
                all_matchups.extend(matchups)
                print(f"  Week {week}: {len(matchups)} matchups")
            return all_matchups

        except Exception as e:
            print(f"Error fetching all matchup summaries: {e}")
            return []

    def get_all_box_scores(self, start_week: int = 1, end_week: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get box scores for all individual scoring periods (days with NBA games).
        
        Args:
            start_week: Starting matchup period (week)
            end_week: Ending matchup period (defaults to current matchup period)
            
        Returns:
            List of all matchups for each individual scoring period
        """
        if end_week is None:
            end_week = getattr(self.league, 'currentMatchupPeriod', 
                            getattr(self.league, 'current_week', 1))
        
        # Get matchup_ids mapping: {1: ['1', '2', '3', '4', '5', '6'], ...}
        matchup_ids = getattr(self.league, 'matchup_ids', {})
        
        all_matchups = []
        total_scoring_periods = 0
        
        print(f"Fetching box scores for weeks {start_week}-{end_week}...")
        
        for week in range(start_week, end_week + 1):
            if week not in matchup_ids:
                continue
                
            # Get all scoring periods for this week
            scoring_periods = matchup_ids[week]
            total_scoring_periods += len(scoring_periods)
            
            for sp_str in scoring_periods:
                scoring_period = int(sp_str)
                
                # Fetch box scores for this specific scoring period
                matchups = self.get_box_scores(week, scoring_period=scoring_period, matchup_total=False)
                all_matchups.extend(matchups)
            
            print(f"  Week {week}: {len(scoring_periods)} scoring periods, {len(matchups) if scoring_periods else 0} matchups/period")
        
        print(f"Total: {total_scoring_periods} scoring periods, {len(all_matchups)} total matchups")
        return all_matchups

    def get_team_roster(self, team_id: int, week: int) -> List[Dict[str, Any]]:
        """Get roster for a specific team and week"""
        try:
            team = next(t for t in self.league.teams if t.team_id == team_id)
            roster = self.league.get_team_data(team_id).roster
            return self._extract_lineup(roster)
        except Exception as e:
            print(f"Error fetching roster for team {team_id}, week {week}: {e}")
            return []
    
    def get_player_stats(self, player_id: int) -> Dict[str, Any]:
        """Get season stats for a specific player"""
        try:
            player = self.league.player_info(playerId=player_id)
            if player:
                return {
                    'name': player.name,
                    'avg_points': player.avg_points,
                    'total_points': player.total_points,
                    'projected_avg_points': getattr(player, 'projected_avg_points', -1),
                    'projected_total_points': getattr(player, 'projected_total_points', -1),
                    'injury_status': getattr(player, 'injuryStatus', 'UNKNOWN'),
                    'position': player.position
                }
        except Exception as e:
            print(f"Error fetching player stats for {player_id}: {e}")
        return {}

    def get_all_player_avg_points(self, matchups: List[Dict]) -> Dict[int, float]:
        """
        Get avg points for all unique players across all matchups (single API call).
        
        Args:
            matchups: List of matchup dicts from get_all_box_scores()
            
        Returns:
            Dict mapping player_id (int) -> avg_points (float)
        """            

        try:
            unique_player_ids = set()
            for matchup in matchups:
                for side in ['home_team', 'away_team']:
                    team_data = matchup.get(side, {})
                    for player in team_data['lineup']:
                        unique_player_ids.add(player['player_id'])

            players_data = self.league.player_info(playerId=list(unique_player_ids))
            return {p.playerId: getattr(p, 'avg_points', -1) for p in players_data}
        except Exception as e:
            print(f"Error fetching all players' avg points: {e}")
            return {}

