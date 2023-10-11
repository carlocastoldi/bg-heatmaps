"""
Scene
    - Create a scene, add root and inset if necessary
    - add actor method
    - special methods
"""
import sys
from pathlib import Path
from vedo import Mesh, Text2D, Assembly
import pyinspect as pi
from rich import print
from loguru import logger
from myterial import amber, orange, orange_darker, salmon

from brainrender import settings
from brainrender.atlas import Atlas
from brainrender.actor import Actor
from brainrender.actors import Volume
from brainrender._utils import return_list_smart, listify
from brainrender._io import load_mesh_from_file


class Scene2D():
    def __init__(
        self,
        root=True,
        atlas_name=None
    ):
        """
        Scene for 2D plots in bgheatmaps.
        It coordinates what should be plotted and how should it look like.
        It is derived from brainrender.scene.Scene and offer the same interface.
        It just cannot render in 3D.

        :param root: bool. If true the brain root mesh is added
        :param atlas_name: str, name of the brainglobe atlas to be used
        """
        logger.debug(
            f"Creating scene with parameters: root: {root}, atlas_name: '{atlas_name}''"
        )

        self.actors = []  # stores all actors in the scene
        self.labels = []  # stores all `labels` actors in scene

        self.atlas = Atlas(atlas_name=atlas_name)

        # Get root mesh
        self.root = self.add_brain_region(
            "root",
            alpha=settings.ROOT_ALPHA,
            color=settings.ROOT_COLOR,
        )
        self.atlas.root = self.root  # give atlas access to root
        self._root_mesh = self.root.mesh.clone()
        if not root:
            self.remove(self.root)

    def __str__(self):
        return f"A `bgheatmaps.scene2d.Scene2D` with {len(self.actors)} actors."

    def __repr__(self):  # pragma: no cover
        return str(self)

    def __repr_html__(self):  # pragma: no cover
        return str(self)

    def add(self, *items, names=None, classes=None, **kwargs):
        """
        General method to add Actors to the scene.

        :param items: vedo.Mesh, Actor, (str, Path).
                If str/path it should be a path to a .obj or .stl file.
                Whatever the input it's turned into an instance of Actor
                before adding it to the scne

        :param names: names to be assigned to the Actors
        :param classs: br_classes to be assigned to the Actors
        :param **kwargs: parameters to be passed to the individual
            loading functions (e.g. to load from file and specify the color)
        """
        names = names or [None for a in items]
        classes = classes or [None for a in items]

        # turn items into Actors
        actors = []
        for item, name, _class in zip(items, listify(names), listify(classes)):
            if item is None:
                continue

            if isinstance(item, (Mesh, Assembly)):
                actors.append(Actor(item, name=name, br_class=_class))

            elif isinstance(item, Text2D):
                # Mark text actors differently because they don't behave like
                # other 3d actors
                actors.append(
                    Actor(
                        item,
                        name=name,
                        br_class=_class,
                        is_text=True,
                        **kwargs,
                    )
                )
            elif pi.utils._class_name(item) == "Volume" and not isinstance(
                item, Volume
            ):
                actors.append(
                    Volume(item, name=name, br_class=_class, **kwargs)
                )
            elif isinstance(item, Actor):
                actors.append(item)

            elif isinstance(item, (str, Path)):
                mesh = load_mesh_from_file(item, **kwargs)
                name = name or Path(item).name
                _class = _class or "from file"
                actors.append(Actor(mesh, name=name, br_class=_class))

            else:
                raise ValueError(
                    f"Unrecognized argument: {item} [{pi.utils._class_name(item)}]"
                )

        # Add to the lists actors
        self.actors.extend(actors)
        return return_list_smart(actors)

    def remove(self, *actors):
        """
        Removes actors from the scene.
        """
        logger.debug(f"Removing {len(actors)} actors from scene")
        for act in actors:
            try:
                self.actors.pop(self.actors.index(act))
            except Exception:
                print(
                    f"Could not remove ({act}, {pi.utils._class_name(act)}) from actors"
                )
    
    def close(self):
        pass

    def get_actors(self, name=None, br_class=None):
        """
        Return's the scene's actors that match some search criteria.

        :param name: strm int or list of str/int, actors' names
        :param br_class: str or list of str, actors br classes
        """
        matches = self.actors
        if name is not None:
            name = listify(name)
            matches = [m for m in matches if m.name in name]
        if br_class is not None:
            br_class = listify(br_class)
            matches = [m for m in matches if m.br_class in br_class]
        return matches

    def add_brain_region(
        self,
        *regions,
        alpha=1,
        color=None,
        hemisphere="both",
    ):
        """
        Dedicated method to add brain regions to render

        :param regions: str. String of regions names
        :param alpha: float. How opaque the regions are rendered.
        :param color: str. If None the atlas default color is used
        :param hemisphere: str.
            - if "both" the complete mesh is returned
            - if "left"/"right" only the corresponding half
                of the mesh is returned
        """
        # avoid adding regions already rendered
        already_in = [
            r.name for r in self.get_actors(br_class="brain region")
        ]
        regions = [r for r in regions if r not in already_in]

        if not regions:  # they were all already rendered
            logger.debug(
                "Not adding any region because they are all already in the 2D scene"
            )
            return None

        logger.debug(
            f"SCENE: Adding {len(regions)} brain regions to scene: {regions}"
        )

        # get regions actors from atlas
        regions = self.atlas.get_region(*regions, alpha=alpha, color=color)
        regions = listify(regions) or []

        # add actors
        actors = self.add(*regions)

        # slice to keep only one hemisphere
        if hemisphere == "right":
            plane = self.atlas.get_plane(
                pos=self.root.centerOfMass(), norm=(0, 0, 1)
            )
        elif hemisphere == "left":
            plane = self.atlas.get_plane(
                pos=self.root.centerOfMass(), norm=(0, 0, -1)
            )

        if hemisphere in ("left", "right"):
            if not isinstance(actors, list):
                actors.cutWithPlane(
                    origin=plane.center,
                    normal=plane.normal,
                )
                actors.cap()
            else:
                for actor in actors:
                    actor.cutWithPlane(
                        origin=plane.center,
                        normal=plane.normal,
                    )
                    actor.cap()

        return actors

    @property
    def content(self):
        """
        Prints an overview of the Actors in the scene.
        """

        actors = pi.Report(
            "Scene actors", accent=salmon, dim=orange, color=orange
        )

        for act in self.actors:
            actors.add(
                f"[bold][{amber}]- {act.name}[/bold][{orange_darker}] (type: [{orange}]{act.br_class}[/{orange}])"
            )

        if "win32" != sys.platform:
            actors.print()
        else:
            print(pi.utils.stringify(actors, maxlen=-1))

    @property
    def clean_actors(self):
        """
        returns only ators that are not Text objects and similar
        """
        return [a for a in self.actors if not a.is_text]

    @property
    def clean_renderables(self):
        """
        Returns meshses only for 'clean actors' (i.e. not text)
        """
        return [a.mesh for a in self.actors if not a.is_text]
