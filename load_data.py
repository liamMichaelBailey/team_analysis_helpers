import polars as pl
import gcsfs

def load_data(
    credentials,
    bucket_name,
    directory,
    competition_edition_id
):
    fs = gcsfs.GCSFileSystem(token=credentials)
    file_path = f"gs://{bucket_name}/{directory}/{competition_edition_id}.parquet"

    with fs.open(file_path) as f:
        dynamic_events_df = (
            pl.read_parquet(
                f,
                use_pyarrow=True,
            )
            .to_pandas()
        )

    file_path = f"gs://{bucket_name}/{directory}/{competition_edition_id}_pop.parquet"

    with fs.open(file_path) as f:
        phases_of_play_df = (
            pl.read_parquet(
                f,
                use_pyarrow=True,
            )
            .to_pandas()
        )

    file_path = f"gs://{bucket_name}/{directory}/{competition_edition_id}_matches.parquet"

    with fs.open(file_path) as f:
        matches_df = (
            pl.read_parquet(
                f,
                use_pyarrow=True,
            )
            .to_pandas()
        )

    file_path = f"gs://{bucket_name}/{directory}/{competition_edition_id}_players_performances.parquet"

    with fs.open(file_path) as f:
        player_performances_df = (
            pl.read_parquet(
                f,
                use_pyarrow=True,
            )
            .to_pandas()
        )

    matches_df['match_duration_minutes'] = (
            matches_df['match_period_1_duration_minutes'] +
            matches_df['match_period_2_duration_minutes']
    )

    return dynamic_events_df, phases_of_play_df, matches_df, player_performances_df