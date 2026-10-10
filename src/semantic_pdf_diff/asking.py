"""The exchange the table queries hold with the model (code review 2026-10-08, architecture 5: tablerules.read and
tablestructure.read wrote it twice, and it drifted: B6, B7, the review's override, "no rows"): ask; check the
answer, and ask again once, shown its problems; then show what it gives for review, again after each revision that
passes the checks, until the model keeps it or the cap is reached. What differs between the queries is a subclass's:
its checks, its texts and what it does with the answer.
"""
from .failures import CallLimitReached, NotRecorded

class Asking:
    """One table query's exchange. A subclass gives its schemas and roles, and the hooks below; start() asks."""
    schema = review_schema = None
    role = review_role = ""  # the recipes' roles: the query's and its review's
    what = ""                # what is asked again: "The rules asked again: ..."

    def __init__(self, core, task, prompt, images):
        self.core, self.task, self.prompt, self.images = core, task, prompt, images

    def start(self):
        self.core.ask(self.role, self.task, self.prompt, self.schema, self.images, self.first)

    def first(self, answer, error):
        self.answered(self.task, answer, error, first=True)

    def second(self, answer, error):
        self.answered(self.task + ":again", answer, error, first=False)

    def answered(self, name, answer, error, first):
        """An answer, named by its task ("<task>:again" for the second), so a task's row is recorded once (B7)."""
        if error is not None:
            if isinstance(error, (CallLimitReached, NotRecorded)):  # nothing learnt: the next run asks again
                return self.not_reached(name, error)
            return self.failed(name, error)
        wrong, applied = self.check(answer)
        if self.settled(name, answer, wrong, first):
            return
        if not wrong:
            return self.review(name, answer, applied)
        if not first:
            return self.fallback(name, answer, wrong)
        self.record(self.task, "partial", [f"The {self.what} asked again: {'; '.join(wrong)}"[:500]])
        again = (self.prompt + "\nYOUR EARLIER ANSWER:\n" + answer.model_dump_json(exclude_defaults=True)
                 + "\nITS PROBLEMS:\n" + "\n".join(f"- {w}" for w in wrong) + "\nAnswer again, mending them.")
        self.core.ask(self.role, self.task + ":again", again, self.schema, self.images, self.second)

    def review(self, named, answer, applied, round_=1, notes=()):
        """The answer's outcome shown to the model, again after each revision that passes the checks, until it keeps
        it or the cap is reached; the last answer passing the checks is used (the owner, 2026-10-07: "a cap of e.g.
        10 will surely be safe ... just keeping the last revision"). use() is told how the review went, in words."""
        cap = self.cap()
        if round_ > cap or not self.reviewable(answer):
            return self.use(named, answer, applied, list(notes), "")
        revised = round_ - 1
        done = f"revised {revised} time{'s' if revised != 1 else ''}" if revised else "kept"

        def finish(result, error):
            self.core.progress.finish("failed" if error is not None else "complete")  # each review asked, finished once
            if error is not None or result is None:  # (code review 2026-10-08, B6: never, so totals never closed)
                return self.use(named, answer, applied, list(notes) + [f"Not reviewed: {error}"[:300]],
                                done if revised else "not reviewed")
            revision = self.revision(result)
            if result.verdict.strip().lower() != "revise" or revision is None:
                return self.use(named, answer, applied, list(notes) + ["Reviewed: kept"], done)
            self.prepare(revision, answer)
            if self.unchanged(revision, answer):  # shown again, it'd repeat itself
                return self.use(named, answer, applied, list(notes) + [self.unchanged_note(result)], done)
            wrong, applied_ = self.check(revision)
            if wrong:
                note = (f"Reviewed: a revision with problems ({'; '.join(wrong)}), the last rules passing the checks "
                        "kept")[:400]
                return self.use(named, answer, applied, list(notes) + [note],
                                done + ", its next revision failing the checks")
            note = f"Reviewed: revised ({'; '.join(result.problems)})"[:400]
            if round_ >= cap:
                return self.use(named, revision, applied_, list(notes) + [note, self.cap_note(cap)],
                                f"revised {round_} time{'s' if round_ != 1 else ''}, the cap reached")
            self.review(named, revision, applied_, round_ + 1, list(notes) + [note])

        self.core.ask(self.review_role, self.review_name(named, round_), self.review_prompt(answer, applied),
                      self.review_schema, self.images, finish)

    # --- the hooks
    def record(self, name, status, issues):
        """A coverage row for one of the query's tasks."""
        raise NotImplementedError

    def check(self, answer):
        """(its problems, what applying it gives, or None)."""
        raise NotImplementedError

    def settled(self, name, answer, wrong, first):
        """Whether the answer settles the query before its checks do (recording how): False by default."""
        return False

    def fallback(self, name, answer, wrong):
        """The second answer's problems too: the query's fallback."""
        raise NotImplementedError

    def not_reached(self, name, error):
        raise NotImplementedError

    def failed(self, name, error):
        raise NotImplementedError

    def cap(self):
        return self.core.s.reviews_tables()

    def reviewable(self, answer):
        raise NotImplementedError

    def review_name(self, named, round_):
        return self.task + ":review" + (str(round_) if round_ > 1 else "")

    def review_prompt(self, answer, applied):
        raise NotImplementedError

    def revision(self, result):
        """The revised answer a review holds, or None."""
        raise NotImplementedError

    def prepare(self, revision, answer):
        """A revision made ready to compare and check, given the answer it revises."""

    def unchanged(self, revision, answer):
        raise NotImplementedError

    def unchanged_note(self, result):
        return "Reviewed: a revision changing nothing, kept"

    def cap_note(self, cap):
        return f"Review cap ({cap}) reached"

    def use(self, named, answer, applied, notes, review):
        """The answer used: notes, what happened, for its row; review, how its review went, in words."""
        raise NotImplementedError
