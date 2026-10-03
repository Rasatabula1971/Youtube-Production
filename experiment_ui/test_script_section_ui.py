from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"


class ScriptSectionUiSlice6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (STATIC / "index.html").read_text(encoding="utf-8")
        cls.script = (STATIC / "app.js").read_text(encoding="utf-8")
        cls.styles = (STATIC / "styles.css").read_text(encoding="utf-8")

    def test_compact_section_review_controls_exist(self):
        for control_id in (
            "scriptSectionTargetStatus",
            "scriptSectionProgress",
            "scriptSectionTarget",
            "scriptSectionNextPending",
            "scriptSectionAccept",
            "scriptSectionLock",
            "scriptSectionUnlock",
            "scriptSectionRework",
            "scriptSectionCancelRework",
            "scriptSectionPrepareRework",
            "scriptSectionGenerate",
            "scriptSectionAlternativeCards",
        ):
            self.assertIn(f'id="{control_id}"', self.html)

        self.assertIn("Prepare rework request", self.html)
        self.assertIn("Next unresolved", self.html)
        self.assertIn("Nothing is applied until you click a choice", self.html)

    def test_section_actions_are_wired_to_existing_api(self):
        self.assertIn('"/api/script-section-review"', self.script)
        self.assertIn(
            'submitScriptSectionAction("PREPARE_REWORK_REQUEST")',
            self.script,
        )
        for action in (
            "ACCEPT",
            "LOCK",
            "UNLOCK",
            "REWORK",
            "CANCEL_REWORK",
            "GENERATE_ALTERNATIVES",
        ):
            self.assertIn(
                f'submitScriptSectionAction("{action}")',
                self.script,
            )

    def test_every_section_mutation_uses_busy_guard(self):
        self.assertIn(
            "if (!current || scriptSectionBusy) return;",
            self.script,
        )
        self.assertIn("scriptSectionBusy = true;", self.script)
        self.assertIn("scriptSectionBusyAction = action;", self.script)
        self.assertIn("scriptSectionBusy = false;", self.script)
        self.assertIn(
            "scriptSectionTarget.disabled = scriptSectionBusy;",
            self.script,
        )
        self.assertIn(
            "scriptReject.disabled = Boolean(scriptSectionBusy);",
            self.script,
        )
        self.assertIn(
            "scriptRework.disabled = Boolean(scriptSectionBusy);",
            self.script,
        )

    def test_whole_script_accept_confirms_and_accepts_open_sections(self):
        # D-105: accepting the whole script after partial section review asks for
        # confirmation, then accepts the remaining sections as they stand.
        self.assertIn(
            "syncWholeScriptAcceptWithSectionState",
            self.script,
        )
        self.assertIn(
            'latestScriptSectionSnapshot.status === "READY_FOR_SECTION_REVIEW"',
            self.script,
        )
        self.assertIn(
            'target.decision !== "ACCEPTED" || target.locked !== true',
            self.script,
        )
        self.assertIn("Accept the whole script as it stands?", self.script)
        self.assertIn("accept_open_sections: acceptOpenSections", self.script)
        self.assertNotIn(
            "Finish the prepared section review before accepting the whole script.",
            self.script,
        )

    def test_selection_and_manual_edit_refresh_whole_script_immediately(self):
        self.assertIn(
            "refreshScriptGateAfterSectionAction",
            self.script,
        )
        self.assertIn(
            'const payload = await api("/api/script-gate");',
            self.script,
        )
        self.assertIn(
            "renderScriptReview(payload, true);",
            self.script,
        )
        self.assertIn(
            "scriptCursor = index;",
            self.script,
        )

    def test_alternatives_are_inline_and_show_claim_provenance(self):
        self.assertIn(
            'data-script-section-selection="ORIGINAL"',
            self.script,
        )
        self.assertIn(
            "data-script-section-selection",
            self.script,
        )
        self.assertIn("Claims used:", self.script)
        self.assertIn("script-section-alternative-grid", self.styles)

    def test_rework_and_manual_edit_validate_before_post(self):
        self.assertIn(
            "Choose a rework reason or enter a specific instruction.",
            self.script,
        )
        self.assertIn(
            "Custom rework requires a specific instruction.",
            self.script,
        )
        self.assertIn(
            "Manual edit must change the selected target.",
            self.script,
        )

    def test_mobile_layout_collapses_alternatives_to_one_column(self):
        self.assertIn(
            ".script-section-alternative-grid",
            self.styles,
        )
        self.assertIn(
            "grid-template-columns: 1fr;",
            self.styles,
        )


    def test_saved_version_restore_controls_exist(self):
        for control_id in (
            "scriptSectionVersions",
            "scriptSectionVersionInfo",
            "scriptSectionVersion",
            "scriptSectionRestore",
        ):
            self.assertIn(f'id="{control_id}"', self.html)
        self.assertIn("Saved versions", self.html)

    def test_restore_posts_version_id_without_a_target_and_confirms(self):
        self.assertIn('submitScriptSectionAction("RESTORE_VERSION", {', self.script)
        self.assertIn(
            'version_id: action === "RESTORE_VERSION" ? extras.version_id : null',
            self.script,
        )
        self.assertIn(
            'target_id: target && action !== "RESTORE_VERSION" ? target.target_id : null',
            self.script,
        )
        self.assertIn('action !== "RESTORE_VERSION" && !target', self.script)
        self.assertIn("window.confirm(", self.script)

    def test_incompatible_versions_cannot_be_chosen(self):
        self.assertIn('(version.compatible ? "" : " disabled")', self.script)
        self.assertIn(
            "scriptSectionRestore.disabled = scriptSectionBusy || !compatible.length;",
            self.script,
        )


if __name__ == "__main__":
    unittest.main()
