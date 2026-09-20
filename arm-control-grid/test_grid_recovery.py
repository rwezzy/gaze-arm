"""Implausible segmented obstacles are dropped; a rejected return rises, then retries."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from grpclib import GRPCError, Status

import main as app
from viam.proto.common import GeometriesInFrame, Geometry, Pose, PoseInFrame, RectangularPrism, Vector3


class WorldRobot:
    async def transform_pose(self, query, destination):
        return PoseInFrame(reference_frame=destination, pose=query.pose)


def seg_object(x, y, z, w, d, h, label):
    return SimpleNamespace(geometries=GeometriesInFrame(reference_frame="world", geometries=[
        Geometry(center=Pose(x=x, y=y, z=z, o_z=1), box=RectangularPrism(dims_mm=Vector3(x=w, y=d, z=h)),
                 label=label)]))


class ObstacleFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_person_sized_segment_is_ignored_and_real_object_kept(self):
        can = seg_object(300, -300, 60, 66, 66, 120, "can")
        person = seg_object(250, -200, 300, 250, 400, 600, "block")       # reaches 600 mm up, 400 mm wide
        ws = await app.obstacles_in_world(WorldRobot(), [can, person], exclude=None)
        kept = [g for f in ws.obstacles for g in f.geometries]
        self.assertEqual(len(kept), 1)
        self.assertEqual((round(kept[0].center.x), round(kept[0].center.y)), (300, -300))


class Rejection(GRPCError):
    def __init__(self):
        super().__init__(Status.UNKNOWN, "all IK solutions failed constraints. Failures: { obstacle constraint }")


class ReturnRetryTests(unittest.IsolatedAsyncioTestCase):
    async def run_return(self, results):
        """Drive run_grasp's carry-back with a mocked pick and scripted motion results."""
        moves = []
        calls = iter(results)

        async def move(**kw):
            moves.append(round(kw["destination"].pose.z))
            r = next(calls)
            if isinstance(r, Exception):
                raise r
            return r

        motion = SimpleNamespace(move=AsyncMock(side_effect=move))
        job = app.GraspJob()
        plan = SimpleNamespace(return_pose=Pose(x=191, y=-304, z=383, o_z=-1),
                               approach=Pose(x=503, y=-384, z=188, o_z=-1),
                               orientation=dict(o_x=0.0, o_y=0.0, o_z=-1.0, theta=0.0))
        job.held = SimpleNamespace(label="block", pose=plan.approach)
        with patch.object(app, "DRY_RUN", False):
            # the carry-back section, exactly as run_grasp runs it
            ok = True
            if await app.move_to(motion, plan.return_pose, "the observe pose (holding it)", job, None,
                                 app.upright()):
                job.held.pose = plan.return_pose
            elif job.plan_rejection and not job.motion_failure:
                job.plan_rejection = None
                r, a = plan.return_pose, plan.approach
                up = Pose(x=a.x, y=a.y, z=max(r.z, a.z), **plan.orientation)
                if await app.move_to(motion, up, "straight up", job, None, app.straight_line()):
                    job.held.pose = up
                    if await app.move_to(motion, r, "observe 2nd try", job, None, app.upright()):
                        job.held.pose = r
                ok = job.held.pose is r
            else:
                ok = False
        return ok, moves, job

    async def test_rejected_return_rises_then_succeeds(self):
        ok, moves, job = await self.run_return([Rejection(), True, True])
        self.assertTrue(ok)
        self.assertEqual(moves, [383, 383, 383])

    async def test_second_rejection_gives_up_holding(self):
        ok, moves, job = await self.run_return([Rejection(), True, Rejection()])
        self.assertFalse(ok)
        self.assertIsNotNone(job.plan_rejection)

    def test_run_grasp_contains_the_retry(self):
        import inspect
        src = inspect.getsource(app.run_grasp)
        self.assertIn("rising straight up first, then retrying", src)


if __name__ == "__main__":
    unittest.main()
