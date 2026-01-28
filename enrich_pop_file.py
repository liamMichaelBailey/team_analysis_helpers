import pandas as pd
import re

IN_POSSESSION_RENAME_MAP = {
    # ids
    "team_in_possession_id": "team_id",
    "team_in_possession_shortname": "team_name",

    "ip_score_start": "team_score_start",
    "oop_score_start": "opponent_score_start",

    "team_in_possession_phase_type": "phase_type",
    "team_in_possession_next_phase": "next_phase_type",

    # spatial
    "team_in_possession_width_start": "team_width_start",
    "team_in_possession_width_end": "team_width_end",
    "team_in_possession_length_start": "team_length_start",
    "team_in_possession_length_end": "team_length_end",

    # enrichments
    "last_defensive_line_height_start_first_team_possession": "opponent_defensive_line_height_start",
    "last_defensive_line_height_end_last_team_possession": "opponent_defensive_line_height_end",

    "n_teammates_ahead_phase_start": "count_players_ahead_phase_start",
    "n_teammates_ahead_phase_end": "count_players_ahead_phase_end",

    # actions
    "n_player_possessions_in_phase": "count_player_possessions",
    "n_passing_option": "count_passing_option",
    "n_cross_receiver": "count_cross_receiver",
    "n_behind": "count_behind",
    "n_coming_short": "count_coming_short",
    "n_dropping_off": "count_dropping_off",
    "n_overlap": "count_overlap",
    "n_pulling_half_space": "count_pulling_half_space",
    "n_pulling_wide": "count_pulling_wide",
    "n_run_ahead_of_the_ball": "count_run_ahead_of_the_ball",
    "n_support": "count_support",
    "n_underlap": "count_underlap",
}

OUT_OF_POSSESSION_RENAME_MAP = {
    "team_out_of_possession_id": "team_id",
    "team_out_of_possession_shortname": "team_name",

    # swap score perspective
    "oop_score_start": "team_score_start",
    "ip_score_start": "opponent_score_start",

    "team_out_of_possession_phase_type": "phase_type",
    "team_out_of_possession_next_phase": "next_phase_type",

    # spatial
    "team_out_of_possession_width_start": "team_width_start",
    "team_out_of_possession_width_end": "team_width_end",
    "team_out_of_possession_length_start": "team_length_start",
    "team_out_of_possession_length_end": "team_length_end",

    # enrichments (defensive line is "team" line when OOP)
    "last_defensive_line_height_start_first_team_possession": "team_defensive_line_height_start",
    "last_defensive_line_height_end_last_team_possession": "team_defensive_line_height_end",

    "n_opponents_ahead_phase_start": "count_players_ahead_phase_start",
    "n_opponents_ahead_phase_end": "count_players_ahead_phase_end",
}


class PhasesEnricherSplitter:
    """
    Handles MULTI-MATCH files.
    Everything is computed per match_id (and per period when available).
    """

    def __init__(
        self,
        phases_df=None,
        dynamic_events_df=None,
        phases_path=None,
        dynamic_events_path=None,
    ):
        if phases_df is None:
            if phases_path is None:
                raise ValueError("Provide phases_df or phases_path.")
            phases_df = pd.read_csv(phases_path)

        if dynamic_events_df is None:
            if dynamic_events_path is None:
                raise ValueError("Provide dynamic_events_df or dynamic_events_path.")
            dynamic_events_df = pd.read_csv(dynamic_events_path)

        self.dynamic_events = dynamic_events_df.copy()
        self.phases = phases_df.copy()

        # pipeline (all multi-match safe)
        self._add_team_out_of_possession_info()  # per match_id
        self._add_next_phase()                   # per match_id (+period)
        self._enrich_from_dynamic_events()       # per match_id (+period)

        self._in_df, self._oop_df = self._split()

    # -----------------------------
    # Helpers
    # -----------------------------
    @staticmethod
    def slugify(s: str) -> str:
        s = str(s).strip().lower()
        s = re.sub(r"\s+", "_", s)
        s = re.sub(r"[^a-z0-9_]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s

    @staticmethod
    def to_bool(series: pd.Series) -> pd.Series:
        if series.dtype == bool:
            return series
        s = series.astype(str).str.strip().str.lower()
        return s.isin(["true", "1", "t", "yes", "y"])

    @staticmethod
    def _rename_safe(df: pd.DataFrame, rename_map: dict) -> pd.DataFrame:
        return df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    @staticmethod
    def _keep(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        return df[[c for c in cols if c in df.columns]].copy()

    # -----------------------------
    # Phases: add OOP team info (MULTI-MATCH SAFE)
    # -----------------------------
    def _add_team_out_of_possession_info(self):
        if "team_out_of_possession_id" in self.phases.columns and "team_out_of_possession_shortname" in self.phases.columns:
            return

        needed = {"match_id", "team_in_possession_id", "team_in_possession_shortname"}
        missing = needed - set(self.phases.columns)
        if missing:
            raise ValueError(f"phases_df missing required columns for OOP mapping: {sorted(missing)}")

        def map_one_match(mdf: pd.DataFrame) -> pd.DataFrame:
            team_ids = mdf["team_in_possession_id"].dropna().unique()
            team_names = mdf["team_in_possession_shortname"].dropna().unique()

            if len(team_ids) != 2 or len(team_names) != 2:
                # Leave NaNs if match is incomplete / bad; don't crash multi-match runs.
                mdf["team_out_of_possession_id"] = pd.NA
                mdf["team_out_of_possession_shortname"] = pd.NA
                return mdf

            id_mapping = {team_ids[0]: team_ids[1], team_ids[1]: team_ids[0]}
            name_mapping = {team_names[0]: team_names[1], team_names[1]: team_names[0]}

            mdf["team_out_of_possession_id"] = mdf["team_in_possession_id"].map(id_mapping)
            mdf["team_out_of_possession_shortname"] = mdf["team_in_possession_shortname"].map(name_mapping)
            return mdf

        self.phases = (
            self.phases
            .groupby("match_id", group_keys=False)
            .apply(map_one_match)
        )

    # -----------------------------
    # Phases: add "next phase" cols (MULTI-MATCH SAFE; prefers match_id+period)
    # -----------------------------
    def _add_next_phase(self):
        needed = {
            "match_id", "frame_start", "frame_end",
            "team_in_possession_id", "team_in_possession_phase_type",
            "team_out_of_possession_id", "team_out_of_possession_phase_type",
        }
        missing = needed - set(self.phases.columns)
        if missing:
            raise ValueError(f"phases_df missing columns needed for next-phase logic: {sorted(missing)}")

        use_period = "period" in self.phases.columns
        group_cols = ["match_id", "period"] if use_period else ["match_id"]

        def add_next(mdf: pd.DataFrame) -> pd.DataFrame:
            mdf = mdf.sort_values(by=["frame_start"]).reset_index(drop=True)
            mdf["team_in_possession_next_phase"] = None
            mdf["team_out_of_possession_next_phase"] = None

            frame_start_to_index = {mdf.loc[i, "frame_start"]: i for i in range(len(mdf))}

            for i in range(len(mdf) - 1):
                current_frame_end = mdf.loc[i, "frame_end"]
                if current_frame_end in frame_start_to_index:
                    next_idx = frame_start_to_index[current_frame_end]

                    if mdf.loc[i, "team_in_possession_id"] == mdf.loc[next_idx, "team_in_possession_id"]:
                        mdf.loc[i, "team_in_possession_next_phase"] = mdf.loc[next_idx, "team_in_possession_phase_type"]
                    else:
                        mdf.loc[i, "team_in_possession_next_phase"] = mdf.loc[next_idx, "team_out_of_possession_phase_type"]

                    if mdf.loc[i, "team_out_of_possession_id"] == mdf.loc[next_idx, "team_out_of_possession_id"]:
                        mdf.loc[i, "team_out_of_possession_next_phase"] = mdf.loc[next_idx, "team_out_of_possession_phase_type"]
                    else:
                        mdf.loc[i, "team_out_of_possession_next_phase"] = mdf.loc[next_idx, "team_in_possession_phase_type"]

            mdf.loc[mdf["team_in_possession_next_phase"].isnull(), "team_in_possession_next_phase"] = "no_next_phase"
            mdf.loc[mdf["team_out_of_possession_next_phase"].isnull(), "team_out_of_possession_next_phase"] = "no_next_phase"
            return mdf

        self.phases = (
            self.phases
            .groupby(group_cols, group_keys=False)
            .apply(add_next)
        )

    # -----------------------------
    # Enrich phases using Dynamic Events (MULTI-MATCH SAFE; uses match_id (+period if available))
    # -----------------------------
    def _enrich_from_dynamic_events(self):
        de = self.dynamic_events.copy()

        dyn_required = {
            "match_id", "phase_index", "event_type", "event_subtype",
            "index",
            "frame_start",
            "team_score", "opponent_team_score",
            "first_player_possession_in_team_possession",
            "last_player_possession_in_team_possession",
            "last_defensive_line_height_start",
            "last_defensive_line_height_end",
            "n_teammates_ahead_start", "n_opponents_ahead_start",
            "n_teammates_ahead_end", "n_opponents_ahead_end",
        }
        missing_dyn = dyn_required - set(de.columns)
        if missing_dyn:
            raise ValueError(f"Dynamic events missing columns: {sorted(missing_dyn)}")

        ph_required = {"match_id", "index", "frame_start"}
        missing_ph = ph_required - set(self.phases.columns)
        if missing_ph:
            raise ValueError(f"Phases missing columns: {sorted(missing_ph)}")

        # normalize types
        # Robust to Categorical dtype
        de["event_subtype"] = (
            de["event_subtype"]
            .astype("string")  # avoids categorical fillna issues
            .fillna("None")
        )
        de["index"] = pd.to_numeric(de["index"], errors="coerce")
        de["frame_start"] = pd.to_numeric(de["frame_start"], errors="coerce")
        de["team_score"] = pd.to_numeric(de["team_score"], errors="coerce")
        de["opponent_team_score"] = pd.to_numeric(de["opponent_team_score"], errors="coerce")

        # 1) event_type counts
        event_type_counts = (
            de.groupby(["match_id", "phase_index", "event_type"])
            .size()
            .reset_index(name="count")
        )
        event_type_pivot = (
            event_type_counts
            .pivot_table(index=["match_id", "phase_index"], columns="event_type", values="count", fill_value=0)
            .reset_index()
        )
        event_type_pivot = event_type_pivot.rename(
            columns=lambda c: f"n_{self.slugify(c)}" if c not in ["match_id", "phase_index"] else c
        )

        # 2) event_subtype counts
        event_subtype_counts = (
            de.groupby(["match_id", "phase_index", "event_subtype"])
            .size()
            .reset_index(name="count")
        )
        event_subtype_pivot = (
            event_subtype_counts
            .pivot_table(index=["match_id", "phase_index"], columns="event_subtype", values="count", fill_value=0)
            .reset_index()
        )
        event_subtype_pivot = event_subtype_pivot.rename(
            columns=lambda c: f"n_{self.slugify(c)}" if c not in ["match_id", "phase_index"] else c
        )

        phase_features = event_type_pivot.merge(event_subtype_pivot, on=["match_id", "phase_index"], how="outer")

        # 3) LDLH + 4) players ahead (from player_possession rows)
        pp = de.loc[de["event_type"] == "player_possession"].copy()
        pp["first_player_possession_in_team_possession"] = self.to_bool(pp["first_player_possession_in_team_possession"])
        pp["last_player_possession_in_team_possession"] = self.to_bool(pp["last_player_possession_in_team_possession"])

        # LDLH from first/last flagged within phase
        first_flagged = pp.loc[pp["first_player_possession_in_team_possession"]].sort_values(["match_id", "phase_index", "index"])
        last_flagged = pp.loc[pp["last_player_possession_in_team_possession"]].sort_values(["match_id", "phase_index", "index"])

        first_ldlh = (
            first_flagged.groupby(["match_id", "phase_index"], as_index=False)
            .first()[["match_id", "phase_index", "last_defensive_line_height_start"]]
            .rename(columns={"last_defensive_line_height_start": "last_defensive_line_height_start_first_team_possession"})
        )
        last_ldlh = (
            last_flagged.groupby(["match_id", "phase_index"], as_index=False)
            .last()[["match_id", "phase_index", "last_defensive_line_height_end"]]
            .rename(columns={"last_defensive_line_height_end": "last_defensive_line_height_end_last_team_possession"})
        )
        phase_features = phase_features.merge(first_ldlh.merge(last_ldlh, on=["match_id", "phase_index"], how="outer"),
                                              on=["match_id", "phase_index"], how="left")

        # players ahead from first/last PP in phase by DE index
        pp_sorted = pp.sort_values(["match_id", "phase_index", "index"])
        pp_first = (
            pp_sorted.groupby(["match_id", "phase_index"], as_index=False)
            .first()[["match_id", "phase_index", "n_teammates_ahead_start", "n_opponents_ahead_start"]]
            .rename(columns={
                "n_teammates_ahead_start": "n_teammates_ahead_phase_start",
                "n_opponents_ahead_start": "n_opponents_ahead_phase_start",
            })
        )
        pp_last = (
            pp_sorted.groupby(["match_id", "phase_index"], as_index=False)
            .last()[["match_id", "phase_index", "n_teammates_ahead_end", "n_opponents_ahead_end"]]
            .rename(columns={
                "n_teammates_ahead_end": "n_teammates_ahead_phase_end",
                "n_opponents_ahead_end": "n_opponents_ahead_phase_end",
            })
        )
        phase_features = phase_features.merge(pp_first.merge(pp_last, on=["match_id", "phase_index"], how="outer"),
                                              on=["match_id", "phase_index"], how="left")

        # 5) score at phase start using nearest PP by frame_start, per match_id (+period if available)
        use_period = ("period" in self.phases.columns) and ("period" in de.columns)
        if use_period:
            by_cols = ["match_id", "period"]
            phase_lookup = self.phases[["match_id", "period", "index", "frame_start"]].copy()
            pp_score = pp[["match_id", "period", "frame_start", "team_score", "opponent_team_score"]].copy()
            phase_lookup = phase_lookup.sort_values(["match_id", "period", "frame_start"])
            pp_score = pp_score.sort_values(["match_id", "period", "frame_start"])
        else:
            by_cols = ["match_id"]
            phase_lookup = self.phases[["match_id", "index", "frame_start"]].copy()
            pp_score = pp[["match_id", "frame_start", "team_score", "opponent_team_score"]].copy()
            phase_lookup = phase_lookup.sort_values(["match_id", "frame_start"])
            pp_score = pp_score.sort_values(["match_id", "frame_start"])

        phase_lookup["frame_start"] = pd.to_numeric(phase_lookup["frame_start"], errors="coerce")
        pp_score["frame_start"] = pd.to_numeric(pp_score["frame_start"], errors="coerce")
        pp_score["team_score"] = pd.to_numeric(pp_score["team_score"], errors="coerce")
        pp_score["opponent_team_score"] = pd.to_numeric(pp_score["opponent_team_score"], errors="coerce")

        phase_score_start = pd.merge_asof(
            phase_lookup,
            pp_score,
            on="frame_start",
            by=by_cols,
            direction="nearest",
            allow_exact_matches=True,
            # Optional:
            # tolerance=125,
        ).rename(columns={
            "team_score": "ip_score_start",
            "opponent_team_score": "oop_score_start",
        })

        # Join score into phase_features via match_id + phase_index (== phases.index)
        phase_features = phase_features.merge(
            phase_score_start[[*by_cols, "index", "ip_score_start", "oop_score_start"]],
            left_on=[*by_cols, "phase_index"],
            right_on=[*by_cols, "index"],
            how="left"
        ).drop(columns=["index"], errors="ignore")

        # Merge phase_features into phases
        self.phases = (
            self.phases.merge(
                phase_features,
                left_on=["match_id", "index"],
                right_on=["match_id", "phase_index"],
                how="left"
            )
            .drop(columns=["phase_index"], errors="ignore")
        )

        # Fill n_* columns as ints
        n_cols = [c for c in self.phases.columns if c.startswith("n_")]
        if n_cols:
            self.phases[n_cols] = self.phases[n_cols].fillna(0).astype(int)

    # -----------------------------
    # Split (returns your chosen subset + renames)
    # -----------------------------
    def _split(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if "team_in_possession_id" not in self.phases.columns or "team_out_of_possession_id" not in self.phases.columns:
            raise ValueError("phases must include team_in_possession_id and team_out_of_possession_id to split.")

        # Include OOP next_phase if you want to rename it
        if "team_out_of_possession_next_phase" not in self.phases.columns:
            self.phases["team_out_of_possession_next_phase"] = "no_next_phase"

        in_possession_cols = [
            "match_id", "index",
            "frame_start", "frame_end",
            "time_start", "time_end",
            "minute_start", "second_start",
            "duration", "period",
            "ip_score_start", "oop_score_start",
            "team_in_possession_id", "team_in_possession_shortname",
            "team_in_possession_phase_type",
            "team_in_possession_next_phase",
            "team_possession_loss_in_phase",
            "team_possession_lead_to_shot",
            "team_possession_lead_to_goal",
            "channel_start", "third_start", "penalty_area_start",
            "channel_end", "third_end", "penalty_area_end",
            "team_in_possession_width_start", "team_in_possession_width_end",
            "team_in_possession_length_start", "team_in_possession_length_end",
            "last_defensive_line_height_start_first_team_possession",
            "last_defensive_line_height_end_last_team_possession",
            "n_teammates_ahead_phase_start", "n_teammates_ahead_phase_end",
            "n_player_possessions_in_phase",
            "n_passing_option",
            "n_cross_receiver",
            "n_behind",
            "n_coming_short",
            "n_dropping_off",
            "n_overlap",
            "n_pulling_half_space",
            "n_pulling_wide",
            "n_run_ahead_of_the_ball",
            "n_support",
            "n_underlap",
        ]
        in_df = self._keep(self.phases, in_possession_cols)
        in_df = self._rename_safe(in_df, IN_POSSESSION_RENAME_MAP)

        out_of_possession_cols = [
            "match_id", "index",
            "frame_start", "frame_end",
            "time_start", "time_end",
            "minute_start", "second_start",
            "duration", "period",
            "ip_score_start", "oop_score_start",
            "team_out_of_possession_id", "team_out_of_possession_shortname",
            "team_out_of_possession_phase_type",
            "team_out_of_possession_next_phase",
            "team_out_of_possession_width_start", "team_out_of_possession_width_end",
            "team_out_of_possession_length_start", "team_out_of_possession_length_end",
            "last_defensive_line_height_start_first_team_possession",
            "last_defensive_line_height_end_last_team_possession",
            "n_opponents_ahead_phase_start", "n_opponents_ahead_phase_end",
        ] + [c for c in self.phases.columns if c.startswith("n_")]
        oop_df = self._keep(self.phases, out_of_possession_cols)
        oop_df = self._rename_safe(oop_df, OUT_OF_POSSESSION_RENAME_MAP)

        return in_df, oop_df

    # -----------------------------
    # Public API
    # -----------------------------
    def get_ip_and_oop(self):
        return self._in_df.copy(), self._oop_df.copy()
