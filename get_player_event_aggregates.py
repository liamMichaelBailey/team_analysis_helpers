import pandas as pd
import numpy as np


def get_player_event_aggregates(dynamic_events_df, player_performances_df, date_from, date_to):
    dynamic_events_df = dynamic_events_df[
        (dynamic_events_df['match_date'] >= date_from) &
        (dynamic_events_df['match_date'] <= date_to)
    ].copy()

    for col in ['associated_off_ball_run_subtype', 'furthest_line_break_type', 'furthest_line_break',
                'event_subtype', 'end_type', 'event_type']:
        if col in dynamic_events_df.columns:
            dynamic_events_df[col] = dynamic_events_df[col].astype(str).replace(['nan', 'None'], np.nan)

    dynamic_events_df['furthest_line_break_info'] = (
        dynamic_events_df['furthest_line_break_type'].fillna('') + '_' +
        dynamic_events_df['furthest_line_break'].fillna('') + '_line'
    )

    player_most_common_position = (
        dynamic_events_df
        .groupby(['player_id', 'team_id'], observed=True)['player_position']
        .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else None)
        .reset_index()
        .rename(columns={'player_position': 'most_common_position'})
    )

    movement_de_aggs = (
        dynamic_events_df[dynamic_events_df['event_type'] == 'passing_option']
        .groupby(['player_id', 'player_name', 'team_id', 'team_shortname', 'team_in_possession_phase_type'], observed=True)
        .agg(
            count_cross_receiver_runs=("associated_off_ball_run_subtype", lambda s: (s == "cross_receiver").sum()),
            count_runs_in_behind=("associated_off_ball_run_subtype", lambda s: (s == "behind").sum()),
            count_runs_ahead_of_the_ball=("associated_off_ball_run_subtype", lambda s: (s == "run_ahead_of_the_ball").sum()),
            count_support_runs=("associated_off_ball_run_subtype", lambda s: (s == "support").sum()),
            count_overlap_runs=("associated_off_ball_run_subtype", lambda s: (s == "overlap").sum()),
            count_underlap_runs=("associated_off_ball_run_subtype", lambda s: (s == "underlap").sum()),
            count_coming_short_runs=("associated_off_ball_run_subtype", lambda s: (s == "coming_short").sum()),
            count_pulling_wide_runs=("associated_off_ball_run_subtype", lambda s: (s == "pulling_wide").sum()),
            count_pulling_half_space_runs=("associated_off_ball_run_subtype", lambda s: (s == "pulling_half_space").sum()),
            count_dropping_off_runs=("associated_off_ball_run_subtype", lambda s: (s == "dropping_off").sum()),
            count_around_first_line=("furthest_line_break_info", lambda s: (s == "around_first_line").sum()),
            count_through_first_line=("furthest_line_break_info", lambda s: (s == "through_first_line").sum()),
            count_around_second_last_line=("furthest_line_break_info", lambda s: (s == "around_second_last_line").sum()),
            count_through_second_last_line=("furthest_line_break_info", lambda s: (s == "through_second_last_line").sum()),
            count_around_last_line=("furthest_line_break_info", lambda s: (s == "around_last_line").sum()),
            count_through_last_line=("furthest_line_break_info", lambda s: (s == "through_last_line").sum()),
        ).reset_index()
    )

    passing_de_aggs = (
        dynamic_events_df[
            (dynamic_events_df['event_type'] == 'passing_option') &
            (dynamic_events_df['targeted'] == True)
        ]
        .groupby(['player_in_possession_id', 'player_in_possession_name', 'team_id', 'team_shortname', 'team_in_possession_phase_type'], observed=True)
        .agg(
            count_pass_attempts_to_cross_receiver_runs=("associated_off_ball_run_subtype", lambda s: (s == "cross_receiver").sum()),
            count_pass_attempts_to_runs_in_behind=("associated_off_ball_run_subtype", lambda s: (s == "behind").sum()),
            count_pass_attempts_to_runs_ahead_of_the_ball=("associated_off_ball_run_subtype", lambda s: (s == "run_ahead_of_the_ball").sum()),
            count_pass_attempts_to_support_runs=("associated_off_ball_run_subtype", lambda s: (s == "support").sum()),
            count_pass_attempts_to_overlap_runs=("associated_off_ball_run_subtype", lambda s: (s == "overlap").sum()),
            count_pass_attempts_to_underlap_runs=("associated_off_ball_run_subtype", lambda s: (s == "underlap").sum()),
            count_pass_attempts_to_coming_short_runs=("associated_off_ball_run_subtype", lambda s: (s == "coming_short").sum()),
            count_pass_attempts_to_pulling_wide_runs=("associated_off_ball_run_subtype", lambda s: (s == "pulling_wide").sum()),
            count_pass_attempts_to_pulling_half_space_runs=("associated_off_ball_run_subtype", lambda s: (s == "pulling_half_space").sum()),
            count_pass_attempts_to_dropping_off_runs=("associated_off_ball_run_subtype", lambda s: (s == "dropping_off").sum()),
            count_pass_attempts_around_first_line=("furthest_line_break_info", lambda s: (s == "around_first_line").sum()),
            count_pass_attempts_through_first_line=("furthest_line_break_info", lambda s: (s == "through_first_line").sum()),
            count_pass_attempts_around_second_last_line=("furthest_line_break_info", lambda s: (s == "around_second_last_line").sum()),
            count_pass_attempts_through_second_last_line=("furthest_line_break_info", lambda s: (s == "through_second_last_line").sum()),
            count_pass_attempts_around_last_line=("furthest_line_break_info", lambda s: (s == "around_last_line").sum()),
            count_pass_attempts_through_last_line=("furthest_line_break_info", lambda s: (s == "through_last_line").sum()),
        ).reset_index()
    )

    obe_de_aggs = (
        dynamic_events_df[dynamic_events_df['event_type'] == 'on_ball_engagement']
        .groupby(['player_id', 'player_name', 'team_id', 'team_shortname', 'team_out_of_possession_phase_type'], observed=True)
        .agg(
            count_on_ball_engagements=("event_type", lambda s: (s == "on_ball_engagement").sum()),
            count_pressing_engagements=("event_subtype", lambda s: (s == "pressing").sum()),
            count_pressure_engagements=("event_subtype", lambda s: (s == "pressure").sum()),
            count_counter_press_engagements=("event_subtype", lambda s: (s == "counter_press").sum()),
            count_recovery_press_engagements=("event_subtype", lambda s: (s == "recovery_press").sum()),
            count_regains=("end_type", lambda s: s.isin(["direct_regain", "indirect_regain"]).sum()),
            count_disruptions=("end_type", lambda s: s.isin(["direct_disruption", "indirect_disruption"]).sum()),
            count_fouls=("end_type", lambda s: (s == "foul").sum()),
            count_reduce_possession_danger=("reduce_possession_danger", lambda s: (s == True).sum()),
            count_stop_possession_danger=("stop_possession_danger", lambda s: (s == True).sum()),
            count_force_backward=("force_backward", lambda s: (s == True).sum()),
            count_beaten_by_possession=("beaten_by_possession", lambda s: (s == True).sum()),
            count_beaten_by_movement=("beaten_by_movement", lambda s: (s == True).sum()),
        ).reset_index()
    )

    passing_de_aggs = passing_de_aggs.rename(columns={
        'player_in_possession_id': 'player_id',
        'player_in_possession_name': 'player_name',
        'team_in_possession_phase_type': 'phase_type',
    })
    movement_de_aggs = movement_de_aggs.rename(columns={'team_in_possession_phase_type': 'phase_type'})
    obe_de_aggs = obe_de_aggs.rename(columns={'team_out_of_possession_phase_type': 'phase_type'})

    player_de_aggs = pd.merge(
        left=movement_de_aggs,
        right=passing_de_aggs,
        on=['player_id', 'player_name', 'team_id', 'team_shortname', 'phase_type'],
        how='outer'
    )
    player_de_aggs = pd.concat([player_de_aggs, obe_de_aggs], ignore_index=True)

    player_performance_aggs = (
        player_performances_df[player_performances_df['match_id'].isin(dynamic_events_df['match_id'].unique())]
        .groupby(['player_id', 'team_id'], observed=True)['playing_time_total_minutes_played']
        .sum().reset_index()
    )

    player_de_aggs = player_de_aggs.merge(player_performance_aggs, on=['player_id', 'team_id'], how='inner')
    player_de_aggs = player_de_aggs.merge(player_most_common_position, on=['player_id', 'team_id'], how='left')

    count_cols = [col for col in player_de_aggs.columns if col.startswith('count_')]
    player_de_aggs[count_cols] = player_de_aggs[count_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

    mins_col = 'playing_time_total_minutes_played'
    player_de_aggs[mins_col] = pd.to_numeric(player_de_aggs[mins_col], errors='coerce')

    player_de_aggs[[m + '_per_90' for m in count_cols]] = (
        player_de_aggs[count_cols].div(player_de_aggs[mins_col].replace(0, np.nan), axis=0) * 90
    )

    player_de_aggs['total_minutes_played'] = player_de_aggs[mins_col]

    return player_de_aggs
