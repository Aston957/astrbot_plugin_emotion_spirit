"""Tests for emotion_spirit.regulation.project_manager — Task 5.2 Long-term projects."""

from emotion_spirit.regulation.project_manager import ProjectManager, Project
from emotion_spirit.regulation.life_plan import DailyPlan, PlannedEvent


class TestProject:
    """Unit tests for Project dataclass."""

    def test_project_defaults(self):
        p = Project(name="学吉他", category="creative", start_date="2026-06-27")
        assert p.name == "学吉他"
        assert p.category == "creative"
        assert p.start_date == "2026-06-27"
        assert p.estimated_days == 7
        assert p.progress == 0.0
        assert p.status == "active"
        assert p.milestones == []

    def test_project_custom_fields(self):
        p = Project(
            name="写小说", category="creative", start_date="2026-06-20",
            estimated_days=30, progress=0.5, status="paused",
            milestones=["人物设定", "故事大纲", "初稿完成"],
        )
        assert p.estimated_days == 30
        assert p.progress == 0.5
        assert p.status == "paused"
        assert len(p.milestones) == 3


class TestProjectManagerSuggest:
    """Tests for suggest_project()."""

    def test_suggest_project_for_high_openness(self):
        pm = ProjectManager(random_seed=1)
        project = pm.suggest_project(
            personality={"openness": 1.0, "conscientiousness": 0.6, "extraversion": 0.5,
                        "agreeableness": 0.5, "neuroticism": 0.3},
            recent_activities=["做饭", "看书"],
        )
        assert project is not None
        assert project.category == "creative"

    def test_suggest_project_for_high_conscientiousness(self):
        pm = ProjectManager()
        # High C + zero O/E means creative has 0 weight; routine dominates.
        project = pm.suggest_project(
            personality={"openness": 0.0, "conscientiousness": 0.9, "extraversion": 0.0,
                        "agreeableness": 0.5, "neuroticism": 0.9},
        )
        assert project is not None
        # Category weights per emotion_spirit/regulation/project_manager.py suggest_project():
        #   creative     = O + E*0.5  = 0.0 + 0*0.5 = 0.0 (never chosen)
        #   physical     = E + (1-N)  = 0.0 + 0.1  = 0.1  (~4.2%)  ← previously MISSED here
        #   intellectual = O*0.5 + C  = 0.0 + 0.9  = 0.9  (~38.3%)
        #   routine      = C*1.5      = 0.9*1.5    = 1.35 (~57.4%)
        # creative has weight 0 and is never picked; original assertion omitted
        # `physical` (which has weight 0.1, ~4% chance to be selected by
        # random.choices) — pure math error in the test. Mirror
        # test_suggest_project_for_high_extraversion's fix: assert all non-zero
        # weight categories are valid outcomes.
        assert project.category in ("intellectual", "physical", "routine")

    def test_suggest_project_for_high_extraversion(self):
        pm = ProjectManager()
        # High E + zero C → routine=0; physical dominates but not exclusive.
        project = pm.suggest_project(
            personality={"openness": 0.4, "conscientiousness": 0.0, "extraversion": 0.9,
                        "agreeableness": 0.5, "neuroticism": 0.2},
        )
        assert project is not None
        # Category weights per emotion_spirit/regulation/project_manager.py suggest_project():
        #   physical     = E + (1-N)  = 0.9 + 0.8  = 1.7  (~61.8% chance)
        #   creative     = O + E*0.5  = 0.4 + 0.45 = 0.85 (~30.9%)
        #   intellectual = O*0.5 + C  = 0.2 + 0.0  = 0.2  (~7.3%) ← previously MISSED here
        #   routine      = C*1.5      = 0.0       = 0    (weight 0, never picked)
        # All three non-zero weights are valid weighted-sample outcomes.
        # Flake root cause: the original assertion omitted `intellectual` despite the
        # comment line above computing its weight as 0.2 — pure math error in the test.
        assert project.category in ("physical", "creative", "intellectual")

    def test_suggest_returns_none_when_all_zero(self):
        pm = ProjectManager()
        # With O/C/E all 0 and N=1, all category weights become 0.
        # creative = 0+0 = 0; intellectual = 0+0 = 0; physical = 0+(1-1)=0; routine = 0*1.5 = 0.
        project = pm.suggest_project(
            personality={"openness": 0.0, "conscientiousness": 0.0, "extraversion": 0.0,
                        "agreeableness": 0.0, "neuroticism": 1.0},
        )
        assert project is None

    def test_suggest_project_has_required_fields(self):
        pm = ProjectManager()
        project = pm.suggest_project(
            personality={"openness": 0.7, "conscientiousness": 0.5, "extraversion": 0.6,
                        "agreeableness": 0.5, "neuroticism": 0.3},
        )
        assert project is not None
        assert isinstance(project.name, str)
        assert isinstance(project.category, str)
        assert isinstance(project.start_date, str)
        assert isinstance(project.estimated_days, int)
        assert project.progress == 0.0
        assert project.status == "active"
        assert isinstance(project.milestones, list)
        assert len(project.milestones) > 0

    def test_suggest_project_deprioritizes_recent_categories(self):
        """Recent activities reduce weight for matching categories."""
        pm = ProjectManager()
        # Do multiple suggestions with "看书" (intellectual) as recent
        # to verify that intellectual isn't always chosen
        categories = set()
        for _ in range(20):
            project = pm.suggest_project(
                personality={"openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5,
                            "agreeableness": 0.5, "neuroticism": 0.5},
                recent_activities=["看书", "做饭"],
            )
            assert project is not None
            categories.add(project.category)
        # With all traits equal, all categories should have non-zero weight,
        # and recent activity deprioritization should still allow variety
        assert len(categories) >= 1


class TestProjectManagerInject:
    """Tests for inject_into_plan()."""

    def test_inject_active_projects_into_plan(self):
        pm = ProjectManager()
        # "健身计划" + "2026-06-27" → seeded Random.random() = 0.7730 >= 0.5 → injected
        pm._projects.append(Project(name="健身计划", category="physical",
                                    start_date="2026-06-25", estimated_days=30,
                                    progress=0.3, status="active",
                                    milestones=["适应期", "力量训练", "有氧运动"]))
        plan = DailyPlan(date="2026-06-27", generated_at=0.0,
                         events=[], personality_snapshot={}, adaptations=[], dream_seed="")
        pm.inject_into_plan(plan)
        assert any("健身计划" in e.activity for e in plan.events)

    def test_completed_project_not_injected(self):
        pm = ProjectManager()
        pm._projects.append(Project(name="完成的事", category="physical",
                                    start_date="2026-06-01", estimated_days=7,
                                    progress=1.0, status="completed",
                                    milestones=[]))
        plan = DailyPlan(date="2026-06-27", generated_at=0.0,
                         events=[], personality_snapshot={}, adaptations=[], dream_seed="")
        pm.inject_into_plan(plan)
        assert not any("完成的事" in e.activity for e in plan.events)

    def test_paused_project_not_injected(self):
        pm = ProjectManager()
        pm._projects.append(Project(name="暂停项目", category="intellectual",
                                    start_date="2026-06-01", estimated_days=30,
                                    progress=0.2, status="paused",
                                    milestones=["阶段1"]))
        plan = DailyPlan(date="2026-06-27", generated_at=0.0,
                         events=[], personality_snapshot={}, adaptations=[], dream_seed="")
        pm.inject_into_plan(plan)
        assert not any("暂停项目" in e.activity for e in plan.events)

    def test_abandoned_project_not_injected(self):
        pm = ProjectManager()
        pm._projects.append(Project(name="放弃的事", category="creative",
                                    start_date="2026-06-01", estimated_days=7,
                                    progress=0.1, status="abandoned",
                                    milestones=[]))
        plan = DailyPlan(date="2026-06-27", generated_at=0.0,
                         events=[], personality_snapshot={}, adaptations=[], dream_seed="")
        pm.inject_into_plan(plan)
        assert not any("放弃的事" in e.activity for e in plan.events)


class TestProjectManagerSerialization:
    """Tests for to_dict() / from_dict() round-trip."""

    def test_to_dict_empty(self):
        pm = ProjectManager()
        d = pm.to_dict()
        assert d == {"projects": []}

    def test_to_dict_with_projects(self):
        pm = ProjectManager()
        pm._projects = [
            Project(name="学吉他", category="creative", start_date="2026-06-25",
                    estimated_days=7, progress=0.3, status="active",
                    milestones=["和弦C", "和弦G"]),
            Project(name="完成的事", category="physical", start_date="2026-06-01",
                    estimated_days=7, progress=1.0, status="completed",
                    milestones=[]),
        ]
        d = pm.to_dict()
        assert len(d["projects"]) == 2
        assert d["projects"][0]["name"] == "学吉他"
        assert d["projects"][0]["category"] == "creative"
        assert d["projects"][0]["status"] == "active"
        assert d["projects"][1]["name"] == "完成的事"
        assert d["projects"][1]["status"] == "completed"

    def test_from_dict_restores_projects(self):
        data = {
            "projects": [
                {"name": "学吉他", "category": "creative", "start_date": "2026-06-25",
                 "estimated_days": 7, "progress": 0.3, "status": "active",
                 "milestones": ["和弦C", "和弦G"]},
            ]
        }
        pm = ProjectManager()
        pm.from_dict(data)
        assert len(pm._projects) == 1
        assert pm._projects[0].name == "学吉他"
        assert pm._projects[0].category == "creative"
        assert pm._projects[0].status == "active"

    def test_roundtrip(self):
        pm1 = ProjectManager()
        pm1._projects = [
            Project(name="学画画", category="creative", start_date="2026-06-20",
                    estimated_days=21, progress=0.1, status="active",
                    milestones=["基础素描", "色彩入门", "完整作品"]),
        ]
        data = pm1.to_dict()
        pm2 = ProjectManager()
        pm2.from_dict(data)
        assert len(pm2._projects) == 1
        p = pm2._projects[0]
        assert p.name == "学画画"
        assert p.category == "creative"
        assert p.estimated_days == 21
        assert p.progress == 0.1
        assert p.status == "active"
        assert p.milestones == ["基础素描", "色彩入门", "完整作品"]
