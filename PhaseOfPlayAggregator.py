import pandas as pd
import numpy as np


class PhasesOfPlayAggregator:
    def __init__(self, phases_of_play_df: pd.DataFrame):
        self.phases_of_play_df = phases_of_play_df.copy()

        # Ensure we have a stable row identifier for counts
        if "index" not in self.phases_of_play_df.columns:
            self.phases_of_play_df = self.phases_of_play_df.reset_index(drop=True)
            self.phases_of_play_df["index"] = self.phases_of_play_df.index

        self._add_team_out_of_possession_info()
        self._add_next_phase()

    def _add_team_out_of_possession_info(self):
        """
        Map missing out-of-possession info PER match_id.
        Assumes each match has (typically) 2 teams. If a match has != 2 teams, mapping may be NaN.
        """
        required_cols = [
            "match_id",
            "team_in_possession_id",
            "team_in_possession_shortname",
        ]
        missing = [c for c in required_cols if c not in self.phases_of_play_df.columns]
        if missing:
            raise ValueError(f"Missing required columns for mapping: {missing}")

        teams = (
            self.phases_of_play_df[["match_id", "team_in_possession_id", "team_in_possession_shortname"]]
            .drop_duplicates()
            .rename(columns={
                "team_in_possession_id": "team_id",
                "team_in_possession_shortname": "team_shortname",
            })
        )

        # Self-join within match to find the "other team"
        pairs = teams.merge(
            teams,
            on="match_id",
            suffixes=("", "_opp"),
            how="inner"
        )

        pairs = pairs[pairs["team_id"] != pairs["team_id_opp"]]

        # If somehow more than 2 teams exist, pick the first "other" deterministically
        pairs = pairs.sort_values(["match_id", "team_id", "team_id_opp"]).drop_duplicates(
            subset=["match_id", "team_id"],
            keep="first"
        )

        # Build per-(match_id, team_id) mapping to opponent
        opp_id_map = pairs.set_index(["match_id", "team_id"])["team_id_opp"]
        opp_name_map = pairs.set_index(["match_id", "team_id"])["team_shortname_opp"]

        key = pd.MultiIndex.from_frame(
            self.phases_of_play_df[["match_id", "team_in_possession_id"]]
            .rename(columns={"team_in_possession_id": "team_id"})
        )

        self.phases_of_play_df["team_out_of_possession_id"] = opp_id_map.reindex(key).to_numpy()
        self.phases_of_play_df["team_out_of_possession_shortname"] = opp_name_map.reindex(key).to_numpy()

    def _add_next_phase(self):
        """
        Compute next-phase fields PER match_id by linking rows where:
        current.frame_end == next.frame_start (within the same match).
        """
        df = self.phases_of_play_df.sort_values(by=["match_id", "frame_start"]).reset_index(drop=True)

        next_cols = [
            "match_id",
            "frame_start",
            "team_in_possession_id",
            "team_in_possession_phase_type",
            "team_out_of_possession_id",
            "team_out_of_possession_phase_type",
        ]

        next_df = df[next_cols].rename(columns={
            "frame_start": "frame_start_next",
            "team_in_possession_id": "team_in_possession_id_next",
            "team_in_possession_phase_type": "team_in_possession_phase_type_next",
            "team_out_of_possession_id": "team_out_of_possession_id_next",
            "team_out_of_possession_phase_type": "team_out_of_possession_phase_type_next",
        })

        # If there are duplicates for a given match_id + frame_start_next, keep the first deterministically
        next_df = next_df.sort_values(["match_id", "frame_start_next"]).drop_duplicates(
            subset=["match_id", "frame_start_next"],
            keep="first"
        )

        merged = df.merge(
            next_df,
            left_on=["match_id", "frame_end"],
            right_on=["match_id", "frame_start_next"],
            how="left"
        )

        # In-possession next phase
        merged["team_in_possession_next_phase"] = np.where(
            merged["team_in_possession_id_next"].isna(),
            "no_next_phase",
            np.where(
                merged["team_in_possession_id"] == merged["team_in_possession_id_next"],
                merged["team_in_possession_phase_type_next"],
                merged["team_out_of_possession_phase_type_next"],
            )
        )

        # Out-of-possession next phase
        merged["team_out_of_possession_next_phase"] = np.where(
            merged["team_out_of_possession_id_next"].isna(),
            "no_next_phase",
            np.where(
                merged["team_out_of_possession_id"] == merged["team_out_of_possession_id_next"],
                merged["team_out_of_possession_phase_type_next"],
                merged["team_in_possession_phase_type_next"],
            )
        )

        self.phases_of_play_df = merged.drop(columns=["frame_start_next"])

    def get_out_of_possession_aggregates(self):
        group_by = [
            "match_id",
            "team_out_of_possession_id",
            "team_out_of_possession_shortname",
            "team_out_of_possession_phase_type",
        ]

        out_of_possession_phase_aggs = self.phases_of_play_df.groupby(group_by, observed=True).agg(
            count=("team_out_of_possession_phase_type", "count"),
            total_time=("duration", "sum"),
            count_player_possessions=("n_player_possessions_in_phase", "sum"),
            count_possession_lost_in_phase=("team_possession_loss_in_phase", "sum"),
            count_possession_lead_to_shot=("team_possession_lead_to_shot", "sum"),
            count_possession_lead_to_goal=("team_possession_lead_to_goal", "sum"),
            avg_start_width=("team_out_of_possession_width_start", "mean"),
            avg_start_length=("team_out_of_possession_length_start", "mean"),
            avg_end_width=("team_out_of_possession_width_end", "mean"),
            avg_end_length=("team_out_of_possession_length_end", "mean"),
        ).reset_index()

        # IMPORTANT: include match_id so multiple matches don't collide
        next_phase_aggs = self.phases_of_play_df.groupby([
            "match_id",
            "team_out_of_possession_id",
            "team_out_of_possession_phase_type",
            "team_out_of_possession_next_phase",
        ]).agg(count=("index", "count")).reset_index()

        # Make mapping key match-aware to avoid collisions across matches
        next_phase_aggs["team_phase_id"] = (
            next_phase_aggs["match_id"].astype(str) + "_" +
            next_phase_aggs["team_out_of_possession_id"].astype(str) + "_" +
            next_phase_aggs["team_out_of_possession_phase_type"].astype(str)
        )

        out_of_possession_phase_aggs["team_phase_id"] = (
            out_of_possession_phase_aggs["match_id"].astype(str) + "_" +
            out_of_possession_phase_aggs["team_out_of_possession_id"].astype(str) + "_" +
            out_of_possession_phase_aggs["team_out_of_possession_phase_type"].astype(str)
        )

        for next_phase in next_phase_aggs["team_out_of_possession_next_phase"].unique():
            sub = next_phase_aggs[next_phase_aggs["team_out_of_possession_next_phase"] == next_phase]
            mapping = dict(zip(sub["team_phase_id"], sub["count"]))
            out_of_possession_phase_aggs[f"count_into_{next_phase}_from"] = (
                out_of_possession_phase_aggs["team_phase_id"].map(mapping)
            )

        out_of_possession_phase_aggs = out_of_possession_phase_aggs.set_index([
            "match_id",
            "team_out_of_possession_id",
            "team_out_of_possession_shortname",
            "team_out_of_possession_phase_type",
        ]).unstack(["team_out_of_possession_phase_type"])

        out_of_possession_phase_aggs.columns = ["{}_{}".format(m, c) for m, c in out_of_possession_phase_aggs.columns]
        out_of_possession_phase_aggs = out_of_possession_phase_aggs.reset_index()

        metric_columns = []
        for phase in [
            "low_block", "medium_block", "high_block", "defending_transition",
            "defending_quick_break", "defending_direct", "chaotic", "defending_set_play"
        ]:
            for metric in [
                "count", "total_time", "count_player_possessions", "count_possession_lost_in_phase",
                "count_possession_lead_to_shot", "count_possession_lead_to_goal", "avg_start_width",
                "avg_start_length", "avg_end_width", "avg_end_length", "count_into_build_up_from",
                "count_into_create_from", "count_into_finish_from", "count_into_transition_from",
                "count_into_quick_break_from", "count_into_direct_from", "count_into_chaotic_from",
                "count_into_low_block_from", "count_into_medium_block_from", "count_into_high_block_from",
                "count_into_defending_quick_break_from", "count_into_defending_transition_from",
                "count_into_defending_direct_from"
            ]:
                col = f"{metric}_{phase}"
                if col not in out_of_possession_phase_aggs.columns:
                    out_of_possession_phase_aggs[col] = np.nan
                metric_columns.append(col)

        return out_of_possession_phase_aggs[group_by[:3] + metric_columns]

    def get_in_possession_aggregates(self):
        group_by = [
            "match_id",
            "team_in_possession_id",
            "team_in_possession_shortname",
            "team_in_possession_phase_type",
        ]

        in_possession_phase_aggs = self.phases_of_play_df.groupby(group_by, observed=True).agg(
            count=("team_in_possession_phase_type", "count"),
            total_time=("duration", "sum"),
            count_player_possessions=("n_player_possessions_in_phase", "sum"),
            count_possession_lost_in_phase=("team_possession_loss_in_phase", "sum"),
            count_possession_lead_to_shot=("team_possession_lead_to_shot", "sum"),
            count_possession_lead_to_goal=("team_possession_lead_to_goal", "sum"),
            avg_start_width=("team_in_possession_width_start", "mean"),
            avg_start_length=("team_in_possession_length_start", "mean"),
            avg_end_width=("team_in_possession_width_end", "mean"),
            avg_end_length=("team_in_possession_length_end", "mean"),
        ).reset_index()

        # IMPORTANT: include match_id so multiple matches don't collide
        next_phase_aggs = self.phases_of_play_df.groupby([
            "match_id",
            "team_in_possession_id",
            "team_in_possession_phase_type",
            "team_in_possession_next_phase",
        ]).agg(count=("index", "count")).reset_index()

        # Make mapping key match-aware to avoid collisions across matches
        next_phase_aggs["team_phase_id"] = (
            next_phase_aggs["match_id"].astype(str) + "_" +
            next_phase_aggs["team_in_possession_id"].astype(str) + "_" +
            next_phase_aggs["team_in_possession_phase_type"].astype(str)
        )

        in_possession_phase_aggs["team_phase_id"] = (
            in_possession_phase_aggs["match_id"].astype(str) + "_" +
            in_possession_phase_aggs["team_in_possession_id"].astype(str) + "_" +
            in_possession_phase_aggs["team_in_possession_phase_type"].astype(str)
        )

        for next_phase in next_phase_aggs["team_in_possession_next_phase"].unique():
            sub = next_phase_aggs[next_phase_aggs["team_in_possession_next_phase"] == next_phase]
            mapping = dict(zip(sub["team_phase_id"], sub["count"]))
            in_possession_phase_aggs[f"count_into_{next_phase}_from"] = (
                in_possession_phase_aggs["team_phase_id"].map(mapping)
            )

        in_possession_phase_aggs = in_possession_phase_aggs.set_index([
            "match_id",
            "team_in_possession_id",
            "team_in_possession_shortname",
            "team_in_possession_phase_type",
        ]).unstack(["team_in_possession_phase_type"])

        in_possession_phase_aggs.columns = ["{}_{}".format(m, c) for m, c in in_possession_phase_aggs.columns]
        in_possession_phase_aggs = in_possession_phase_aggs.reset_index()

        metric_columns = []
        for phase in ["build_up", "create", "finish", "transition", "quick_break", "direct", "chaotic", "set_play"]:
            for metric in [
                "count", "total_time", "count_player_possessions", "count_possession_lost_in_phase",
                "count_possession_lead_to_shot", "count_possession_lead_to_goal", "avg_start_width",
                "avg_start_length", "avg_end_width", "avg_end_length", "count_into_build_up_from",
                "count_into_create_from", "count_into_finish_from", "count_into_transition_from",
                "count_into_quick_break_from", "count_into_direct_from", "count_into_chaotic_from",
                "count_into_low_block_from", "count_into_medium_block_from", "count_into_high_block_from",
                "count_into_defending_quick_break_from", "count_into_defending_transition_from",
                "count_into_defending_direct_from"
            ]:
                col = f"{metric}_{phase}"
                if col not in in_possession_phase_aggs.columns:
                    in_possession_phase_aggs[col] = np.nan
                metric_columns.append(col)

        return in_possession_phase_aggs[group_by[:3] + metric_columns]
