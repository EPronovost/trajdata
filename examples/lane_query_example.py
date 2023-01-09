"""
This is an example of how to extend a batch with lane information
"""

from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
from torch.utils.data import DataLoader
from tqdm import tqdm

from trajdata import AgentBatch, AgentType, UnifiedDataset
from trajdata.data_structures.batch_element import AgentBatchElement, SceneBatchElement
from trajdata.maps import VectorMap
from trajdata.maps.vec_map_elements import RoadLane
from trajdata.utils.arr_utils import batch_nd_transform_points_np
from trajdata.visualization.vis import plot_agent_batch


def get_closest_lane_point(element: AgentBatchElement) -> np.ndarray:
    """Closest lane for predicted agent."""

    # Transform from agent coordinate frame to world coordinate frame.
    vector_map: VectorMap = element.vec_map
    world_from_agent_tf = np.linalg.inv(element.agent_from_world_tf)
    agent_future_xy_world = batch_nd_transform_points_np(
        element.agent_future_np[:, :2], world_from_agent_tf
    )

    # Use cached kdtree to find closest lane point
    lane_points_world = []
    for xy_world in agent_future_xy_world:
        point_xyz = np.array([[xy_world[0], xy_world[1], 0.0]])
        closest_lane: RoadLane = vector_map.get_closest_lane(point_xyz.squeeze(axis=0))
        lane_points_world.append(closest_lane.center.project_onto(point_xyz))

    lane_points_world = np.concatenate(lane_points_world, axis=0)

    # Transform lane points to agent coordinate frame
    lane_points = batch_nd_transform_points_np(
        lane_points_world[:, :2], element.agent_from_world_tf
    )

    return lane_points


def main():
    dataset = UnifiedDataset(
        desired_data=[
            "nusc_mini-mini_train",
            "lyft_sample-mini_val",
        ],
        centric="agent",
        desired_dt=0.1,
        history_sec=(3.2, 3.2),
        future_sec=(4.8, 4.8),
        only_types=[AgentType.VEHICLE],
        agent_interaction_distances=defaultdict(lambda: 30.0),
        incl_robot_future=False,
        incl_raster_map=True,
        raster_map_params={
            "px_per_m": 2,
            "map_size_px": 224,
            "offset_frac_xy": (-0.5, 0.0),
        },
        incl_vector_map=True,
        num_workers=0,
        verbose=True,
        data_dirs={  # Remember to change this to match your filesystem!
            "nusc_mini": "~/datasets/nuScenes",
            "lyft_sample": "~/datasets/lyft/scenes/sample.zarr",
        },
        # A dictionary that contains functions that generate our custom data.
        # Can be any function and has access to the batch element.
        extras={
            "closest_lane_point": get_closest_lane_point,
        },
    )

    print(f"# Data Samples: {len(dataset):,}")

    dataloader = DataLoader(
        dataset,
        batch_size=4,
        shuffle=False,
        collate_fn=dataset.get_collate_fn(),
        num_workers=0,
    )

    # Visualize selected examples
    num_plots = 3
    batch_idxs = [10876, 10227, 1284]
    # batch_idxs = random.sample(range(len(dataset)), num_plots)
    batch: AgentBatch = dataset.get_collate_fn(pad_format="right")(
        [dataset[i] for i in batch_idxs]
    )
    assert "closest_lane_point" in batch.extras

    for batch_i in range(num_plots):
        ax = plot_agent_batch(
            batch, batch_idx=batch_i, legend=False, show=False, close=False
        )
        lane_points = batch.extras["closest_lane_point"][batch_i]
        ax.plot(
            lane_points[:, 0],
            lane_points[:, 1],
            "o-",
            markersize=3,
            label="Lane points",
        )
        ax.legend(loc="best", frameon=True)
    plt.show()
    plt.close("all")

    # Scan through dataset
    batch: AgentBatch
    for idx, batch in enumerate(tqdm(dataloader)):
        assert "closest_lane_point" in batch.extras
        if idx > 50:
            break


if __name__ == "__main__":
    main()