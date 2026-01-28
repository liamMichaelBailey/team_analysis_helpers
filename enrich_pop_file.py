import pandas as pd
import re

IN_POSSESSION_RENAME_MAP = {
    # ids
    "team_in_possession_id": "team_id",
    "team_in_possession_shortname": "team_name",

    "ip_score_start": "team_score_start",
    "oop_score_start": "opponent_score_start",

    "team_in_possession_phase_type": "phase_type",
    "team_in_possession_next_phase": 'next_phase_type',

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


class PhasesEnricherSplitter:
    """
    Enriches a phases_of_play dataframe using a dynamic_events dataframe, then returns
    two dataframes:
      - in_possession_df
      - out_of_possession_df

    No saving. You can pass either dataframes directly OR file paths.
    """

    def __init__(
        self,
        phases_df = None,
        dynamic_events_df = None,
        phases_path = None,
        dynamic_events_path = None,
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

        # Step pipeline
        self._add_team_out_of_possession_info()
        self._add_next_phase()
        self._enrich_from_dynamic_events()

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

    # -----------------------------
    # Phases: add OOP team info
    # -----------------------------
    def _add_team_out_of_possession_info(self):
        if "team_out_of_possession_id" in self.phases.columns and "team_out_of_possession_shortname" in self.phases.columns:
            return

        if "team_in_possession_id" not in self.phases.columns or "team_in_possession_shortname" not in self.phases.columns:
            raise ValueError("phases_df must include team_in_possession_id and team_in_possession_shortname.")

        team_ids = self.phases["team_in_possession_id"].dropna().unique()
        team_names = self.phases["team_in_possession_shortname"].dropna().unique()

        if len(team_ids) != 2 or len(team_names) != 2:
            raise ValueError(
                "Expected exactly 2 teams in phases_df to map out-of-possession team info."
            )

        id_mapping = {team_ids[0]: team_ids[1], team_ids[1]: team_ids[0]}
        name_mapping = {team_names[0]: team_names[1], team_names[1]: team_names[0]}

        self.phases["team_out_of_possession_id"] = self.phases["team_in_possession_id"].map(id_mapping)
        self.phases["team_out_of_possession_shortname"] = self.phases["team_in_possession_shortname"].map(name_mapping)

    # -----------------------------
    # Phases: add "next phase" cols
    # -----------------------------
    def _add_next_phase(self):
        needed = {
            "frame_start", "frame_end",
            "team_in_possession_id", "team_in_possession_phase_type",
            "team_out_of_possession_id", "team_out_of_possession_phase_type",
        }
        missing = needed - set(self.phases.columns)
        if missing:
            raise ValueError(f"phases_df missing columns needed for next-phase logic: {sorted(missing)}")

        self.phases = self.phases.sort_values(by=["frame_start"]).reset_index(drop=True)
        self.phases["team_in_possession_next_phase"] = None
        self.phases["team_out_of_possession_next_phase"] = None

        frame_start_to_index = {self.phases.loc[i, "frame_start"]: i for i in range(len(self.phases))}

        for i in range(len(self.phases) - 1):
            current_frame_end = self.phases.loc[i, "frame_end"]
            if current_frame_end in frame_start_to_index:
                next_idx = frame_start_to_index[current_frame_end]

                if self.phases.loc[i, "team_in_possession_id"] == self.phases.loc[next_idx, "team_in_possession_id"]:
                    self.phases.loc[i, "team_in_possession_next_phase"] = self.phases.loc[next_idx, "team_in_possession_phase_type"]
                else:
                    self.phases.loc[i, "team_in_possession_next_phase"] = self.phases.loc[next_idx, "team_out_of_possession_phase_type"]

                if self.phases.loc[i, "team_out_of_possession_id"] == self.phases.loc[next_idx, "team_out_of_possession_id"]:
                    self.phases.loc[i, "team_out_of_possession_next_phase"] = self.phases.loc[next_idx, "team_out_of_possession_phase_type"]
                else:
                    self.phases.loc[i, "team_out_of_possession_next_phase"] = self.phases.loc[next_idx, "team_in_possession_phase_type"]

        self.phases.loc[self.phases["team_in_possession_next_phase"].isnull(), "team_in_possession_next_phase"] = "no_next_phase"
        self.phases.loc[self.phases["team_out_of_possession_next_phase"].isnull(), "team_out_of_possession_next_phase"] = "no_next_phase"

    # -----------------------------
    # Enrich phases using Dynamic Events
    # -----------------------------
    def _enrich_from_dynamic_events(self):
        """
        Enrich self.phases using self.dynamic_events (DE).

        Adds (phase-level):
          - n_{event_type} counts
          - n_{event_subtype} counts
          - LDLH from first/last team-possession flags (within each phase)
          - players ahead of ball at phase start/end (split) from first/last PP in phase (by DE index)
          - score at phase start (ip_score_start, oop_score_start) using nearest PP by frame_start (robust)
        """
        de = self.dynamic_events.copy()

        # -----------------------------
        # Column checks
        # -----------------------------
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

        # -----------------------------
        # Normalize types
        # -----------------------------
        de["event_subtype"] = de["event_subtype"].fillna("None")
        de["index"] = pd.to_numeric(de["index"], errors="coerce")
        de["frame_start"] = pd.to_numeric(de["frame_start"], errors="coerce")
        de["team_score"] = pd.to_numeric(de["team_score"], errors="coerce")
        de["opponent_team_score"] = pd.to_numeric(de["opponent_team_score"], errors="coerce")

        # -----------------------------
        # 1) Count event_type per phase -> n_{type}
        # -----------------------------
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

        # -----------------------------
        # 2) Count event_subtype per phase -> n_{subtype}
        # -----------------------------
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

        # -----------------------------
        # 3) LDLH from first/last possession-in-team-possession flags (within each phase)
        # -----------------------------
        pp = de.loc[de["event_type"] == "player_possession"].copy()
        pp["first_player_possession_in_team_possession"] = self.to_bool(
            pp["first_player_possession_in_team_possession"])
        pp["last_player_possession_in_team_possession"] = self.to_bool(pp["last_player_possession_in_team_possession"])

        first_flagged = pp.loc[pp["first_player_possession_in_team_possession"]].sort_values(
            ["match_id", "phase_index", "index"]
        )
        last_flagged = pp.loc[pp["last_player_possession_in_team_possession"]].sort_values(
            ["match_id", "phase_index", "index"]
        )

        first_ldlh = (
            first_flagged.groupby(["match_id", "phase_index"], as_index=False)
            .first()[["match_id", "phase_index", "last_defensive_line_height_start"]]
            .rename(
                columns={"last_defensive_line_height_start": "last_defensive_line_height_start_first_team_possession"})
        )

        last_ldlh = (
            last_flagged.groupby(["match_id", "phase_index"], as_index=False)
            .last()[["match_id", "phase_index", "last_defensive_line_height_end"]]
            .rename(columns={"last_defensive_line_height_end": "last_defensive_line_height_end_last_team_possession"})
        )

        ldlh_phase = first_ldlh.merge(last_ldlh, on=["match_id", "phase_index"], how="outer")
        phase_features = phase_features.merge(ldlh_phase, on=["match_id", "phase_index"], how="left")

        # -----------------------------
        # 4) Players ahead at PHASE start & end (split) from first/last PP in phase (by DE index)
        # -----------------------------
        pp_sorted = pp.sort_values(["match_id", "phase_index", "index"])

        pp_first_in_phase = (
            pp_sorted.groupby(["match_id", "phase_index"], as_index=False)
            .first()[["match_id", "phase_index", "n_teammates_ahead_start", "n_opponents_ahead_start"]]
            .rename(columns={
                "n_teammates_ahead_start": "n_teammates_ahead_phase_start",
                "n_opponents_ahead_start": "n_opponents_ahead_phase_start",
            })
        )

        pp_last_in_phase = (
            pp_sorted.groupby(["match_id", "phase_index"], as_index=False)
            .last()[["match_id", "phase_index", "n_teammates_ahead_end", "n_opponents_ahead_end"]]
            .rename(columns={
                "n_teammates_ahead_end": "n_teammates_ahead_phase_end",
                "n_opponents_ahead_end": "n_opponents_ahead_phase_end",
            })
        )

        players_ahead_phase = pp_first_in_phase.merge(pp_last_in_phase, on=["match_id", "phase_index"], how="outer")
        for c in [
            "n_teammates_ahead_phase_start", "n_opponents_ahead_phase_start",
            "n_teammates_ahead_phase_end", "n_opponents_ahead_phase_end",
        ]:
            players_ahead_phase[c] = pd.to_numeric(players_ahead_phase[c], errors="coerce")

        phase_features = phase_features.merge(players_ahead_phase, on=["match_id", "phase_index"], how="left")

        # -----------------------------
        # 5) Score at PHASE START (robust) using nearest PP by frame_start
        # -----------------------------
        # Build PP score table
        use_period = ("period" in self.phases.columns) and ("period" in de.columns)

        if use_period:
            pp_score = de.loc[
                de["event_type"] == "player_possession",
                ["match_id", "period", "frame_start", "team_score", "opponent_team_score"]
            ].copy()
            phase_lookup = self.phases[["match_id", "period", "index", "frame_start"]].copy()
            by_cols = ["match_id", "period"]
            phase_lookup = phase_lookup.sort_values(["match_id", "period", "frame_start"])
            pp_score = pp_score.sort_values(["match_id", "period", "frame_start"])
        else:
            pp_score = de.loc[
                de["event_type"] == "player_possession",
                ["match_id", "frame_start", "team_score", "opponent_team_score"]
            ].copy()
            phase_lookup = self.phases[["match_id", "index", "frame_start"]].copy()
            by_cols = ["match_id"]
            phase_lookup = phase_lookup.sort_values(["match_id", "frame_start"])
            pp_score = pp_score.sort_values(["match_id", "frame_start"])

        # Ensure numeric
        phase_lookup["frame_start"] = pd.to_numeric(phase_lookup["frame_start"], errors="coerce")
        pp_score["frame_start"] = pd.to_numeric(pp_score["frame_start"], errors="coerce")
        pp_score["team_score"] = pd.to_numeric(pp_score["team_score"], errors="coerce")
        pp_score["opponent_team_score"] = pd.to_numeric(pp_score["opponent_team_score"], errors="coerce")

        # Nearest possession to phase start
        phase_score_start = pd.merge_asof(
            phase_lookup,
            pp_score,
            on="frame_start",
            by=by_cols,
            direction="nearest",
            allow_exact_matches=True,
            # Optional safety:
            # tolerance=125,  # ~5s at 25fps
        )

        phase_score_start = phase_score_start.rename(columns={
            "team_score": "ip_score_start",
            "opponent_team_score": "oop_score_start",
        })

        # Merge score into phase_features (align on phase_index == phases.index)
        phase_features = phase_features.merge(
            phase_score_start[["match_id", "index", "ip_score_start", "oop_score_start"]],
            left_on=["match_id", "phase_index"],
            right_on=["match_id", "index"],
            how="left"
        ).drop(columns=["index"], errors="ignore")

        # -----------------------------
        # 6) Merge phase_features into phases (phases.index == phase_index)
        # -----------------------------
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

        # Keep continuous cols numeric (NaN allowed)
        for c in [
            "last_defensive_line_height_start_first_team_possession",
            "last_defensive_line_height_end_last_team_possession",
            "n_teammates_ahead_phase_start",
            "n_opponents_ahead_phase_start",
            "n_teammates_ahead_phase_end",
            "n_opponents_ahead_phase_end",
            "ip_score_start",
            "oop_score_start",
        ]:
            if c in self.phases.columns:
                self.phases[c] = pd.to_numeric(self.phases[c], errors="coerce")

    # -----------------------------
    # Split
    # -----------------------------
    def _split(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if "team_in_possession_id" not in self.phases.columns or "team_out_of_possession_id" not in self.phases.columns:
            raise ValueError("phases must include team_in_possession_id and team_out_of_possession_id to split.")

        def keep(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
            return df[[c for c in cols if c in df.columns]].copy()

        def _rename_safe(df: pd.DataFrame, rename_map: dict) -> pd.DataFrame:
            return df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        # -----------------------------
        # In-possession columns
        # -----------------------------
        in_possession_cols = [
                                 # identifiers
                                 "match_id",
                                 "index",  # phase id
                                 "team_in_possession_id",
                                 "team_in_possession_shortname",

                                 # timing
                                 "frame_start", "frame_end",
                                 "time_start", "time_end",
                                 "minute_start", "second_start",
                                 "duration", "period",
                                 "ip_score_start", "oop_score_start",

                                # phase info
                                 "team_in_possession_phase_type",

                                 # outcomes
                                 "team_in_possession_next_phase",
                                 "team_possession_loss_in_phase",
                                 "team_possession_lead_to_shot",
                                 "team_possession_lead_to_goal",

                                 # spatial (IP)
                                 "channel_start", "third_start", "penalty_area_start",
                                 "channel_end", "third_end", "penalty_area_end",
                                 "team_in_possession_width_start",
                                 "team_in_possession_width_end",
                                 "team_in_possession_length_start",
                                 "team_in_possession_length_end",
                                 "last_defensive_line_height_start_first_team_possession",
                                 "last_defensive_line_height_end_last_team_possession",
                                 "n_teammates_ahead_phase_start",
                                 "n_teammates_ahead_phase_end",

                                 # actions
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

        in_df = keep(self.phases, in_possession_cols)
        in_df = _rename_safe(in_df, IN_POSSESSION_RENAME_MAP)

        # -----------------------------
        # Out-of-possession columns
        # -----------------------------
        out_of_possession_cols = [
                                     # identifiers
                                     "match_id",
                                     "index",
                                     "team_out_of_possession_id",
                                     "team_out_of_possession_shortname",
                                     "team_out_of_possession_phase_type",
                                     "team_out_of_possession_phase_type_id",

                                     # timing
                                     "frame_start", "frame_end",
                                     "time_start", "time_end",
                                     "minute_start", "second_start",
                                     "period", "duration"

                                     # spatial (OOP)
                                     "team_out_of_possession_width_start",
                                     "team_out_of_possession_width_end",
                                     "team_out_of_possession_length_start",
                                     "team_out_of_possession_length_end",

                                     # enrichments (same signals, opponent perspective)
                                     "last_defensive_line_height_start_first_team_possession",
                                     "last_defensive_line_height_end_last_team_possession",
                                     "n_opponents_ahead_phase_start",
                                     "n_opponents_ahead_phase_end",
                                 ] + [c for c in self.phases.columns if c.startswith("n_")]

        oop_df = keep(self.phases, out_of_possession_cols)


        return in_df, oop_df

    # -----------------------------
    # Public API
    # -----------------------------
    def get_in_possession_df(self) -> pd.DataFrame:
        return self._in_df.copy()

    def get_out_of_possession_df(self) -> pd.DataFrame:
        return self._oop_df.copy()

    def get_ip_and_oop(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        return self.get_in_possession_df(), self.get_out_of_possession_df()