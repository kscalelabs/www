import {
  Camera,
  Object3D,
  Plane,
  Ray,
  Raycaster,
  Scene,
  Vector2,
  Vector3,
} from "three";
import { URDFJoint } from "urdf-loader";

export function isJoint(o: unknown): boolean {
  const j = o as URDFJoint;
  return j && j.isURDFJoint && j.jointType !== "fixed";
}

function findNearestJoint(child: Object3D): URDFJoint | null {
  let curr: Object3D | null = child;
  while (curr) {
    if (isJoint(curr)) {
      return curr as URDFJoint;
    }
    curr = curr.parent;
  }
  return null;
}

export class URDFDragControls {
  enabled: boolean;
  scene: Scene;
  raycaster: Raycaster;
  initialGrabPoint: Vector3;
  hitDistance: number;
  hovered: URDFJoint | null;
  manipulating: URDFJoint | null;

  // Add the variables as private properties
  protected prevHitPoint: Vector3;
  protected newHitPoint: Vector3;
  protected pivotPoint: Vector3;
  protected tempVector: Vector3;
  protected tempVector2: Vector3;
  protected projectedStartPoint: Vector3;
  protected projectedEndPoint: Vector3;
  protected plane: Plane;

  protected draggable: boolean;

  constructor(scene: Scene, draggable = false) {
    this.enabled = true;
    this.scene = scene;
    this.raycaster = new Raycaster();
    this.initialGrabPoint = new Vector3();

    this.hitDistance = -1;
    this.hovered = null;
    this.manipulating = null;

    // Initialize the private variables
    this.prevHitPoint = new Vector3();
    this.newHitPoint = new Vector3();
    this.pivotPoint = new Vector3();
    this.tempVector = new Vector3();
    this.tempVector2 = new Vector3();
    this.projectedStartPoint = new Vector3();
    this.projectedEndPoint = new Vector3();
    this.plane = new Plane();

    this.draggable = draggable;
  }

  update() {
    const { raycaster, hovered, manipulating, scene } = this;

    if (manipulating) {
      return;
    }

    scene.updateMatrixWorld();

    let hoveredJoint: URDFJoint | null = null;
    const intersections = raycaster.intersectObjects(scene.children, true);
    if (intersections.length !== 0) {
      const hit = intersections[0];
      this.hitDistance = hit.distance;
      hoveredJoint = findNearestJoint(hit.object);
      if (hoveredJoint) {
        this.initialGrabPoint.copy(hit.point);
      }
    }

    if (hoveredJoint !== hovered) {
      if (hovered) {
        this.onUnhover(hovered);
      }
      this.hovered = hoveredJoint;
      if (hoveredJoint) {
        this.onHover(hoveredJoint);
      }
    }
  }

  updateJoint(joint: URDFJoint, angle: number) {
    joint.setJointValue(angle);
  }

  onDragStart(joint: URDFJoint) {}

  onDragEnd(joint: URDFJoint) {}

  onHover(joint: URDFJoint) {}

  onUnhover(joint: URDFJoint) {}

  onClick(joint: URDFJoint) {}

  getRevoluteDelta(
    joint: URDFJoint,
    startPoint: Vector3,
    endPoint: Vector3,
  ): number {
    // set up the plane
    this.tempVector
      .copy(joint.axis)
      .transformDirection(joint.matrixWorld)
      .normalize();
    this.pivotPoint.set(0, 0, 0).applyMatrix4(joint.matrixWorld);
    this.plane.setFromNormalAndCoplanarPoint(this.tempVector, this.pivotPoint);

    // project the drag points onto the plane
    this.plane.projectPoint(startPoint, this.projectedStartPoint);
    this.plane.projectPoint(endPoint, this.projectedEndPoint);

    // get the directions relative to the pivot
    this.projectedStartPoint.sub(this.pivotPoint);
    this.projectedEndPoint.sub(this.pivotPoint);

    this.tempVector.crossVectors(
      this.projectedStartPoint,
      this.projectedEndPoint,
    );

    const direction = Math.sign(this.tempVector.dot(this.plane.normal));
    return direction * this.projectedEndPoint.angleTo(this.projectedStartPoint);
  }

  getPrismaticDelta(
    joint: URDFJoint,
    startPoint: Vector3,
    endPoint: Vector3,
  ): number {
    this.tempVector.subVectors(endPoint, startPoint);
    this.plane.normal
      .copy(joint.axis)
      .transformDirection(joint.parent!.matrixWorld)
      .normalize();

    return this.tempVector.dot(this.plane.normal);
  }

  moveRay(toRay: Ray) {
    const { raycaster, hitDistance, manipulating } = this;
    const { ray } = raycaster;

    if (manipulating && this.draggable) {
      ray.at(hitDistance, this.prevHitPoint);
      toRay.at(hitDistance, this.newHitPoint);

      let delta = 0;
      if (
        manipulating.jointType === "revolute" ||
        manipulating.jointType === "continuous"
      ) {
        delta = this.getRevoluteDelta(
          manipulating,
          this.prevHitPoint,
          this.newHitPoint,
        );
      } else if (manipulating.jointType === "prismatic") {
        delta = this.getPrismaticDelta(
          manipulating,
          this.prevHitPoint,
          this.newHitPoint,
        );
      }

      if (delta) {
        this.updateJoint(manipulating, manipulating.angle.valueOf() + delta);
      }
    }

    this.raycaster.ray.copy(toRay);
    this.update();
  }

  setGrabbed(grabbed: boolean) {
    const { hovered, manipulating } = this;

    if (grabbed) {
      if (manipulating !== null || hovered === null) {
        return;
      }

      this.manipulating = hovered;
      this.onDragStart(hovered);
    } else {
      if (this.manipulating === null) {
        return;
      }

      this.onDragEnd(this.manipulating);
      const manipulating = this.manipulating;
      this.manipulating = null;
      this.update();
      if (manipulating == this.hovered) {
        this.onClick(manipulating!);
      }
    }
  }
}

export class PointerURDFDragControls extends URDFDragControls {
  camera: Camera;
  domElement: HTMLElement;

  private _mouseDown: (e: MouseEvent) => void;
  private _mouseMove: (e: MouseEvent) => void;
  private _mouseUp: (e: MouseEvent) => void;

  constructor(scene: Scene, camera: Camera, domElement: HTMLElement) {
    super(scene);
    this.camera = camera;
    this.domElement = domElement;

    const raycaster = new Raycaster();
    const mouse = new Vector2();

    const updateMouse = (e: MouseEvent) => {
      const rect = domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.x) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.y) / rect.height) * 2 + 1;
    };

    this._mouseDown = (e: MouseEvent) => {
      updateMouse(e);
      raycaster.setFromCamera(mouse, this.camera);
      this.moveRay(raycaster.ray);
      this.setGrabbed(true);
    };

    this._mouseMove = (e: MouseEvent) => {
      updateMouse(e);
      raycaster.setFromCamera(mouse, this.camera);
      this.moveRay(raycaster.ray);
    };

    this._mouseUp = (e: MouseEvent) => {
      updateMouse(e);
      raycaster.setFromCamera(mouse, this.camera);
      this.moveRay(raycaster.ray);
      this.setGrabbed(false);
    };

    domElement.addEventListener("mousedown", this._mouseDown);
    domElement.addEventListener("mousemove", this._mouseMove);
    domElement.addEventListener("mouseup", this._mouseUp);
  }

  getRevoluteDelta(
    joint: URDFJoint,
    startPoint: Vector3,
    endPoint: Vector3,
  ): number {
    const { camera, initialGrabPoint } = this;

    // set up the plane
    this.tempVector
      .copy(joint.axis)
      .transformDirection(joint.matrixWorld)
      .normalize();
    this.pivotPoint.set(0, 0, 0).applyMatrix4(joint.matrixWorld);
    this.plane.setFromNormalAndCoplanarPoint(this.tempVector, this.pivotPoint);

    this.tempVector.copy(camera.position).sub(initialGrabPoint).normalize();

    // if looking into the plane of rotation
    if (Math.abs(this.tempVector.dot(this.plane.normal)) > 0.3) {
      return super.getRevoluteDelta(joint, startPoint, endPoint);
    } else {
      // get the up direction
      this.tempVector.set(0, 1, 0).transformDirection(camera.matrixWorld);

      // get points projected onto the plane of rotation
      this.plane.projectPoint(startPoint, this.projectedStartPoint);
      this.plane.projectPoint(endPoint, this.projectedEndPoint);

      this.tempVector.set(0, 0, -1).transformDirection(camera.matrixWorld);
      this.tempVector.cross(this.plane.normal);
      this.tempVector2.subVectors(endPoint, startPoint);

      return this.tempVector.dot(this.tempVector2);
    }
  }

  dispose() {
    const { domElement } = this;
    domElement.removeEventListener("mousedown", this._mouseDown);
    domElement.removeEventListener("mousemove", this._mouseMove);
    domElement.removeEventListener("mouseup", this._mouseUp);
  }
}
