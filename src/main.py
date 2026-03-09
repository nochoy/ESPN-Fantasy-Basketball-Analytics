"""
ESPN Fantasy Basketball Analytics
Main entry point for running the analytics script
"""

import os
import sys
import argparse
from typing import Optional
from dotenv import load_dotenv

from espn_client import ESPNClient
from calculations import FantasyCalculator
from google_sheets import GoogleSheetsExporter

load_dotenv()


def run_analytics(league_id: Optional[int] = None, year: Optional[int] = None,
                  skip_export: bool = False, weeks: Optional[int] = None, 
                  sheet_name: Optional[str] = None):
    """
    Run the full analytics pipeline
    
    Args:
        league_id: ESPN league ID (optional, defaults to env var)
        year: Season year (optional, defaults to env var)
        skip_export: Skip Google Sheets export
        sheet_name: Name of Google Sheet to create/use
        weeks: Number of weeks to analyze (default: all completed weeks)
    """
    print("=" * 60)
    print("🏀 ESPN Fantasy Basketball Analytics")
    print("=" * 60)
    
    # Step 1: Connect to ESPN
    print("\n📡 Connecting to ESPN...")
    try:
        client = ESPNClient(league_id=league_id, year=year)
        league_info = client.get_league_info()
        print(f"  League: {league_info['name']}")
        print(f"  Season: {league_info['season']}")
        print(f"  Teams: {league_info['teams_count']}")
        print(f"  Current Week: {league_info['current_week']}")
        print(f"  Regular Season Weeks: {league_info['reg_season_weeks']}")
        print(f"  Playoff Rounds: {league_info['playoff_rounds']}")
        print(f"  Total Weeks: {league_info['total_weeks']}")
        print(f"  Season Phase: {league_info['season_phase']}")
        print(f"  Scoring Type: {league_info['scoring_type']}")
    except Exception as e:
        print(f"❌ Error connecting to ESPN: {e}")
        print("\nMake sure your credentials are set correctly in .env file:")
        print("  - ESPN_LEAGUE_ID")
        print("  - ESPN_S2 (for private leagues)")
        print("  - ESPN_SWID (for private leagues)")
        sys.exit(1)
    
    
    # Step 2: Get team data
    print("\n👥 Fetching team data...")
    teams = client.get_teams()
    print(f"  ✓ Loaded {len(teams)} teams")
    # print("teams: ", teams)

    # Step 3: Get matchup data
    print("\n📊 Fetching matchup data...")
    end_week = weeks or league_info['current_week']
    matchup_summaries = client.get_all_matchup_summaries(start_week=1, end_week=end_week)
    matchups = client.get_all_box_scores(start_week=1, end_week=end_week)
    player_avg_points = client.get_all_player_avg_points(matchups)

    print(f"  ✓ Loaded {len(matchup_summaries)} total matchup summaries")
    print(f"  ✓ Loaded {len(matchups)} total matchups")
    # print("matchup_summary[0]: ", (matchup_summaries[0]))
    # print("matchup[0]: ", (matchups[0]))
    # print("box scores: ", matchups)
    
    # Step 4: Calculate all statistics
    print("\n🧮 Calculating statistics...")
    calculator = FantasyCalculator(matchup_summaries=matchup_summaries, matchups=matchups, teams=teams, player_avg_points=player_avg_points)
    stats = calculator.generate_all_stats()
    
    # Display summary
    print("\n" + "=" * 60)
    print("📋 STATS SUMMARY")
    print("=" * 60)
    
    print("\n🏆 Current Standings:")
    print(stats['standings'].to_string(index=False))

    print("\n💪 Strength of Schedule (lower = tougher):")
    print(stats['toughness_summary'].to_string(index=False))
    
    print("\n📊 Weekly Rankings (PF/PA by Week):")
    print(stats['weekly_rankings'].head(12).to_string(index=False))
    
    print("\n📈 Cumulative Stats:")
    print(stats['cumulative_stats'].head(17).to_string(index=False))
    
    print("\n🤕 Injury Stats Summary:")
    injury_summary = stats['injury_stats'].groupby(['team_id', 'team_name']).agg({
        # 'cumulative_games_missed_injury': 'last',
        # 'cumulative_games_missed_ir': 'last',
        # 'cumulative_total_games_missed': 'last',
        # 'cumulative_lost_points_injury': 'last',
        # 'cumulative_lost_points_ir': 'last',
        # 'cumulative_total_lost_points': 'last',
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
    print("TOTAL INJURY STATS:")
    print(injury_summary[['team_id', 'team_name', 'games_missed_injury', 'games_missed_ir', 'total_games_missed', 'lost_points_injury', 'lost_points_ir', 'total_lost_points']].to_string(index=False))
    print("FINAL AVERAGE INJUSRY STATS:")
    print(injury_summary[['team_id', 'team_name', 'avg_games_missed_injury', 'avg_games_missed_ir', 'avg_total_games_missed', 'avg_lost_points_injury', 'avg_lost_points_ir', 'avg_total_lost_points']].to_string(index=False))
    
    injury_weekly = stats['injury_stats'].groupby(['week', 'team_id', 'team_name']).sum().reset_index()
    print("\n\nWEEKLY TOTALS INJURY STATS: \n")
    print(injury_weekly[['week', 'team_id', 'team_name', 'games_missed_injury', 'games_missed_ir', 'total_games_missed', 'lost_points_injury', 'lost_points_ir', 'total_lost_points']].head(24).to_string(index=False))
    print("CUMULATIVE AVERAGE INJURY STATS:\n")
    print(injury_weekly[['week', 'team_id', 'team_name', 'avg_games_missed_injury', 'avg_games_missed_ir', 'avg_total_games_missed', 'avg_lost_points_injury', 'avg_lost_points_ir', 'avg_total_lost_points']].head(24).to_string(index=False))
    print("CUMULATIVE INJURY STATS:\n")
    print(injury_weekly[['week', 'team_id', 'team_name', 'cumulative_games_missed_injury', 'cumulative_games_missed_ir', 'cumulative_total_games_missed', 'cumulative_lost_points_injury', 'cumulative_lost_points_ir', 'cumulative_total_lost_points']].head(24).to_string(index=False))
    # print(injury_summary.to_string(index=False))
    # print("INJURY STSA:\n", stats['injury_stats'][stats['injury_stats']['team_id'] == 1].to_string())
    # print("INJURY STSA:\n", stats['injury_stats'][stats['injury_stats']['week'] == 1].to_string())

    
    
    # Step 5: Export to Google Sheets
    if not skip_export:
        print("\n📤 Exporting to Google Sheets...")
        try:
            exporter = GoogleSheetsExporter(sheet_name=sheet_name)
            exporter.export_all_stats(stats)
            # stats = {}
            exporter.create_overview(stats)
        except Exception as e:
            print(f"❌ Error exporting to Google Sheets: {e}")
            print("\nMake sure your Google credentials are set up correctly:")
            print("  1. Download service account JSON from Google Cloud Console")
            print("  2. Save it to config/google-credentials.json")
            print("  3. Set GOOGLE_SHEET_NAME in .env file or use CLI arg")
    else:
        print("\n⏭️  Skipping Google Sheets export (--skip-export flag used)")
    
    print("\n" + "=" * 60)
    print("✅ Analytics Complete!")
    print("=" * 60)


def setup_env():
    """Create .env file from template if it doesn't exist"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    example_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.example')
    
    if not os.path.exists(env_path) and os.path.exists(example_path):
        print("Creating .env file from template...")
        with open(example_path, 'r') as f:
            template = f.read()
        with open(env_path, 'w') as f:
            f.write(template)
        print(f"✓ Created {env_path}")
        print("  Please edit it with your credentials before running again.")
        return False
    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='ESPN Fantasy Basketball Analytics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py                                        # Run with .env settings
  python src/main.py --weeks 10                             # Only analyze first 10 weeks
  python src/main.py --skip-export                          # Don't export to Google Sheets
  python src/main.py --league-id 12345                      # Override league ID
  python src/main.py --sheet-name "Fantasy Analytics"       # Existing or desired Google sheet name
        """
    )
    
    parser.add_argument('--league-id', type=int, 
                       help='ESPN League ID (overrides .env)')
    parser.add_argument('--year', type=int, 
                       help='Season year (overrides .env)')
    parser.add_argument('--weeks', type=int, 
                       help='Number of weeks to analyze')
    parser.add_argument('--skip-export', action='store_true',
                       help='Skip Google Sheets export')
    parser.add_argument('--sheet-name', type=str, 
                       help='Name of Google sheet to create or use (overrides .env)')
    parser.add_argument('--setup', action='store_true',
                       help='Create .env file from template')
    
    args = parser.parse_args()
    
    # Setup mode
    if args.setup:
        setup_env()
        return
    
    # Check if .env exists
    if not setup_env():
        return
    
    # Run analytics
    run_analytics(
        league_id=args.league_id,
        year=args.year,
        skip_export=args.skip_export,
        weeks=args.weeks,
        sheet_name=args.sheet_name,
    )


if __name__ == '__main__':
    main()
