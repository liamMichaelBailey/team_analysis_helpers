import gcsfs
import polars as pl
import numpy as np
import pandas as pd


def load_data_(credentials, bucket_name, competition_edition_id, directory=None):
    fs = gcsfs.GCSFileSystem(token=credentials)
    base = f"{bucket_name}/{directory}" if directory else bucket_name

    def _read(suffix):
        path = f"gs://{base}/{competition_edition_id}_{suffix}.parquet"
        with fs.open(path) as f:
            return pl.read_parquet(f, use_pyarrow=True).to_pandas()

    dynamic_events_df = _read("dynamic_events")
    phases_of_play_df = _read("phases_of_play")
    matches_df = _read("match_metadata")
    player_performances_df = _read("player_performance_metadata")

    matches_df['match_duration_minutes'] = (
        matches_df['match_period_1_duration_minutes'] +
        matches_df['match_period_2_duration_minutes']
    )

    dynamic_events_df = pd.merge(dynamic_events_df, matches_df, on='match_id', how='inner')

    pos_map = {
        'GK': 'Goalkeeper',
        'LCB': 'Central Defender', 'CB': 'Central Defender', 'RCB': 'Central Defender',
        'LWB': 'Left Full Back', 'LB': 'Left Full Back',
        'RWB': 'Right Full Back', 'RB': 'Right Full Back',
        'LDM': 'Midfield', 'DM': 'Midfield', 'RDM': 'Midfield',
        'LM': 'Midfield', 'AM': 'Midfield', 'RM': 'Midfield',
        'LW': 'Left Wide Attacker', 'LF': 'Left Wide Attacker',
        'RW': 'Right Wide Attacker', 'RF': 'Right Wide Attacker',
        'CF': 'Center Forward'
    }

    dynamic_events_df['player_position_group'] = dynamic_events_df['player_position'].map(pos_map).fillna('Other Position')
    dynamic_events_df['player_in_possession_position_group'] = dynamic_events_df['player_in_possession_position'].map(pos_map).fillna('Other Position')

    dynamic_events_df['date_time'] = pd.to_datetime(dynamic_events_df['date_time'])
    dynamic_events_df['match_date'] = dynamic_events_df['date_time']
    dynamic_events_df['match_name'] = (
        dynamic_events_df['home_team_name'].astype(str) + ' v ' +
        dynamic_events_df['away_team_name'].astype(str) + ' (' +
        dynamic_events_df['date_time'].dt.strftime('%d/%m/%Y') + ')'
    )
    dynamic_events_df['match_video_name'] = (
        dynamic_events_df['date_time'].dt.strftime('%Y%m%d') + '_' +
        dynamic_events_df['home_team_short_name'].astype(str) + '_' +
        dynamic_events_df['away_team_short_name'].astype(str)
    )

    dynamic_events_df['opposition_team_id'] = np.where(
        dynamic_events_df['team_id'] == dynamic_events_df['home_team_id'],
        dynamic_events_df['away_team_id'],
        dynamic_events_df['home_team_id']
    )

    dynamic_events_df['competition_edition_id'] = dynamic_events_df['competition_edition_id'].astype(int)

    phases_of_play_df = pd.merge(phases_of_play_df, matches_df, on='match_id', how='inner')

    phases_of_play_df['date_time'] = pd.to_datetime(phases_of_play_df['date_time'])
    phases_of_play_df['match_date'] = phases_of_play_df['date_time']
    phases_of_play_df['match_name'] = (
        phases_of_play_df['home_team_name'].astype(str) + ' v ' +
        phases_of_play_df['away_team_name'].astype(str) + ' (' +
        phases_of_play_df['date_time'].dt.strftime('%Y-%m-%d %H:%M:%S') + ')'
    )

    phases_of_play_df['team_out_of_possession_id'] = np.where(
        phases_of_play_df['team_in_possession_id'] == phases_of_play_df['home_team_id'],
        phases_of_play_df['away_team_id'],
        phases_of_play_df['home_team_id']
    )
    phases_of_play_df['team_out_of_possession_shortname'] = np.where(
        phases_of_play_df['team_in_possession_id'] == phases_of_play_df['home_team_id'],
        phases_of_play_df['away_team_short_name'].astype(str),
        phases_of_play_df['home_team_short_name'].astype(str)
    )

    phases_of_play_df['competition_edition_id'] = phases_of_play_df['competition_edition_id'].astype(int)

    bool_map = {'true': True, 'false': False, 'True': True, 'False': False}
    dynamic_events_df.replace(bool_map, inplace=True)
    phases_of_play_df.replace(bool_map, inplace=True)

    return dynamic_events_df, phases_of_play_df, matches_df, player_performances_df
