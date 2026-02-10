from PhaseOfPlayAggregator import PhasesOfPlayAggregator


def get_phase_of_play_aggregates(
        phases_of_play_df,
        matches_df,
        date_from,
        date_to
):
    phases_of_play_df = phases_of_play_df[
        (phases_of_play_df['match_date'] >= date_from) &
        (phases_of_play_df['match_date'] <= date_to)
    ]

    pop_aggregator = PhasesOfPlayAggregator(phases_of_play_df=phases_of_play_df)

    ip_phase_match_aggs = pop_aggregator.get_in_possession_aggregates()
    ip_phase_match_aggs['match_duration_minutes'] = ip_phase_match_aggs['match_id'].map(
        dict(zip(matches_df['match_id'],
                 matches_df['match_duration_minutes']))
    )

    ip_phase_season_aggs = (
        ip_phase_match_aggs
        .groupby([
            "team_in_possession_id",
            "team_in_possession_shortname"],
            observed=True
        )
        .agg(
            n_matches=("match_id", "nunique"),
            minutes_played=("match_duration_minutes", "sum"),
            total_build_up_duration=("total_time_build_up", "sum"),
            total_create_duration=("total_time_create", "sum"),
            total_finish_duration=("total_time_finish", "sum"),

            count_build_up=("count_build_up", "sum"),
            count_create=("count_create", "sum"),
            count_finish=("count_finish", "sum"),
            count_direct=("count_direct", "sum"),
            count_transition=("count_transition", "sum"),
            count_quick_break=("count_quick_break", "sum"),
            count_chaotic=("count_chaotic", "sum"),

            # Build Up metrics.
            count_into_create_from_build_up=("count_into_create_from_build_up", "sum"),
            count_into_direct_from_build_up=("count_into_direct_from_build_up", "sum"),
            count_possession_loss_in_build_up=("count_possession_lost_in_phase_build_up", "sum"),
            avg_width_build_up=("avg_end_width_build_up", "mean"),
            avg_length_build_up=("avg_end_length_build_up", "mean"),

            # Create metrics.
            count_into_finish_from_create=("count_into_finish_from_create", "sum"),
            count_into_build_up_from_create=("count_into_build_up_from_create", "sum"),
            count_possession_loss_in_create=("count_possession_lost_in_phase_create", "sum"),
            avg_width_create=("avg_end_width_create", "mean"),
            avg_length_create=("avg_end_length_create", "mean"),

            # Finish metrics.
            count_possession_lead_to_shot_finish=("count_possession_lead_to_shot_finish", "sum"),
            count_into_create_from_finish=("count_into_create_from_finish", "sum"),
            count_possession_loss_in_finish=("count_possession_lost_in_phase_finish", "sum"),
            avg_width_finish=("avg_end_width_finish", "mean"),
            avg_length_finish=("avg_end_length_finish", "mean"),

        )
        .reset_index()
    )

    for phase in ['build_up', 'create', 'finish', 'direct', 'transition', 'chaotic']:
        ip_phase_season_aggs[f'count_{phase}_phases_per_90'] = (
                                                                       ip_phase_season_aggs[f'count_{phase}'] /
                                                                       ip_phase_season_aggs['minutes_played']
                                                               ) * 90

    for phase in ['build_up', 'create', 'finish']:
        ip_phase_season_aggs[f'possession_loss_in_{phase}_percentage'] = (
                                                                                 ip_phase_season_aggs[
                                                                                     f'count_possession_loss_in_{phase}'] /
                                                                                 ip_phase_season_aggs[f'count_{phase}']
                                                                         ) * 100

    ip_phase_season_aggs['progressed_to_create_from_build_up_percentage'] = (
                                                                                    ip_phase_season_aggs[
                                                                                        'count_into_create_from_build_up'] /
                                                                                    ip_phase_season_aggs[
                                                                                        'count_build_up']
                                                                            ) * 100

    ip_phase_season_aggs['progressed_to_direct_from_build_up_percentage'] = (
                                                                                    ip_phase_season_aggs[
                                                                                        'count_into_direct_from_build_up'] /
                                                                                    ip_phase_season_aggs[
                                                                                        'count_build_up']
                                                                            ) * 100

    ip_phase_season_aggs['progressed_to_finish_from_create_percentage'] = (
                                                                                  ip_phase_season_aggs[
                                                                                      'count_into_finish_from_create'] /
                                                                                  ip_phase_season_aggs['count_create']
                                                                          ) * 100

    ip_phase_season_aggs['played_back_to_build_up_from_create_percentage'] = (
                                                                                     ip_phase_season_aggs[
                                                                                         'count_into_build_up_from_create'] /
                                                                                     ip_phase_season_aggs[
                                                                                         'count_create']
                                                                             ) * 100

    ip_phase_season_aggs['finish_lead_to_shot_percentage'] = (
                                                                     ip_phase_season_aggs[
                                                                         'count_possession_lead_to_shot_finish'] /
                                                                     ip_phase_season_aggs['count_finish']
                                                             ) * 100

    ip_phase_season_aggs['played_back_to_create_from_finish_percentage'] = (
                                                                                   ip_phase_season_aggs[
                                                                                       'count_into_create_from_finish'] /
                                                                                   ip_phase_season_aggs['count_finish']
                                                                           ) * 100

    metrics = [
        'count_build_up_phases_per_90',
        'count_create_phases_per_90',
        'count_finish_phases_per_90',
        'count_direct_phases_per_90',
        'count_transition_phases_per_90',
        'count_chaotic_phases_per_90',
        'avg_width_build_up',
        'avg_length_build_up',
        'avg_width_create',
        'avg_length_create',
        'avg_width_finish',
        'avg_length_finish',
        'possession_loss_in_build_up_percentage',
        'possession_loss_in_create_percentage',
        'possession_loss_in_finish_percentage',
        'progressed_to_create_from_build_up_percentage',
        'progressed_to_direct_from_build_up_percentage',
        'progressed_to_finish_from_create_percentage',
        'played_back_to_build_up_from_create_percentage',
        'finish_lead_to_shot_percentage',
        'played_back_to_create_from_finish_percentage'
    ]

    for m in metrics:
        ip_phase_season_aggs[m + '_competition_score'] = (
                (ip_phase_season_aggs[m] - ip_phase_season_aggs[m].mean())
                / ip_phase_season_aggs[m].std()
        )

    return ip_phase_season_aggs


