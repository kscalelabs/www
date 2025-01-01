import React, { useEffect, useRef, } from "react";
import * as THREE from "three";
import { Material } from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader";
import URDFLoader, { URDFJoint, URDFLink, URDFRobot } from "urdf-loader";
import { PointerURDFDragControls, isJoint } from "./DragControl";
import { UntarredFile } from "./untar";

interface JointControl {
  name: string;
  min: number;
  max: number;
  value: number;
}

type Orientation = "Z-up" | "Y-up" | "X-up";

const URDFRenderer: React.FC<{
  urdfContent: string;
  files: UntarredFile[];
  onJointClicked: (a: URDFJoint) => void;
}> = ({ urdfContent, files, onJointClicked }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const worldRef = useRef<THREE.Object3D | null>(null);
  const robotRef = useRef<THREE.Object3D | null>(null);
  const animationRef = useRef<number | null>(null);
  const dragControlsRef = useRef<PointerURDFDragControls | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color(0xffffff);

    const world = new THREE.Object3D();
    worldRef.current = world;
    scene.add(world);

    const camera = new THREE.PerspectiveCamera(
      50,
      containerRef.current.clientWidth / containerRef.current.clientHeight,
      0.1,
      1000,
    );
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(
      containerRef.current.clientWidth,
      containerRef.current.clientHeight,
    );
    containerRef.current.appendChild(renderer.domElement);

    // Lighting setup
    const frontLight = new THREE.DirectionalLight(0xffffff, 0.7);
    frontLight.position.set(1, 1, 1);
    scene.add(frontLight);

    const backLight = new THREE.DirectionalLight(0xffffff, 0.3);
    backLight.position.set(-1, -1, -1);
    scene.add(backLight);

    const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
    scene.add(ambientLight);

    const loader = new URDFLoader();
    loader.loadMeshCb = (path, _manager, onComplete) => {
      const fileContent = files.find((f) => f.name.endsWith(path))?.content;
      if (fileContent) {
        const geometry = new STLLoader().parse(fileContent.buffer);
        const material = new THREE.MeshPhongMaterial({
          color: 0xffffff,
          side: THREE.DoubleSide,
        });
        const mesh = new THREE.Mesh(geometry, material);
        onComplete(mesh);
      } else {
        onComplete(new THREE.Object3D());
      }
    };

    const robot = loader.parse(urdfContent);
    robotRef.current = robot;
    world.add(robot);

    // Center and scale the robot
    const box = new THREE.Box3().setFromObject(robot);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const scale = 5 / maxDim;
    robot.scale.multiplyScalar(scale);
    robot.position.sub(center.multiplyScalar(scale));

    // Position camera in front of the robot
    const distance = 10;
    camera.position.set(0, distance / 4, -distance);
    camera.lookAt(new THREE.Vector3(0, 0, 0));
    // controls.update();

    // Collect joint information
    const joints: JointControl[] = [];
    robot.traverse((child) => {
      if ("isURDFJoint" in child && child.isURDFJoint) {
        const joint = child as URDFJoint;
        const initialValue =
          (Number(joint.limit.lower) + Number(joint.limit.upper)) / 2;
        joints.push({
          name: joint.name,
          min: Number(joint.limit.lower),
          max: Number(joint.limit.upper),
          value: initialValue,
        });
        joint.setJointValue(initialValue);
      }
    });
    // Sort joints alphabetically by name
    joints.sort((a, b) => a.name.localeCompare(b.name));

    // Collect link information.
    const links: URDFLink[] = [];
    robot.traverse((child) => {
      if ("isURDFLink" in child && child.isURDFLink) {
        const link = child as URDFLink;
        links.push(link);
      }
    });

    const animate = () => {
      requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!containerRef.current) return;
      camera.aspect = containerRef.current.clientWidth /
        containerRef.current.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(
        containerRef.current.clientWidth,
        containerRef.current.clientHeight,
      );
    };

    window.addEventListener("resize", handleResize);

    const updateOrientation = (newOrientation: Orientation) => {
      if (robotRef.current) {
        const robot = robotRef.current;

        // Reset rotations
        robot.rotation.set(0, 0, 0);

        switch (newOrientation) {
          case "Y-up":
            robot.rotateX(-Math.PI / 2);
            break;
          case "X-up":
            robot.rotateZ(Math.PI / 2);
            break;
            // 'Z-up' is the default, no rotation needed
        }
        robot.updateMatrixWorld();
      }
    };

    updateOrientation("Z-up");
    const updateMaterials = (mesh: URDFRobot) => {
      mesh.traverse((child:any) => {
        const c = child as THREE.Mesh;
        if (c.isMesh) {
          c.castShadow = true;
          c.receiveShadow = true;

          if (c.material) {
            const mats = (Array.isArray(c.material) ? c.material : [c.material])
              .map((mesh:Material) => {
                if (mesh instanceof THREE.MeshBasicMaterial) {
                  mesh = new THREE.MeshPhongMaterial();
                }

                const m = mesh as THREE.MeshPhongMaterial;
                if (m.map) {
                  m.map.colorSpace = THREE.SRGBColorSpace;
                }

                return m;
              });
            c.material = mats.length === 1 ? mats[0] : mats;
          }
        }
      });
    };
    updateMaterials(robot);

    const highlightMaterial = new THREE.MeshPhongMaterial({
      shininess: 10,
      color: 0xffffff,
      emissive: 0xffffff,
      emissiveIntensity: 0.25,
    });

    const highlightLinkGeometry = (m:THREE.Object3D, revert: boolean) => {
      const traverse = (c: any) => {
        // Set or revert the highlight color
        if (c.type === "Mesh") {
          if (revert) {
            c.material = c.__origMaterial;
            delete c.__origMaterial;
          } else {
            c.__origMaterial = c.material;
            c.material = highlightMaterial;
          }
        }

        // Look into the children and stop if the next child is
        // another joint
        if (c === m || !isJoint(c)) {
          for (let i = 0; i < c.children.length; i++) {
            const child = c.children[i];
            if (!child.isURDFCollider) {
              traverse(c.children[i]);
            }
          }
        }
      };
      traverse(m);
    };

    animate();
    world.updateMatrixWorld(true);
    const dragControls = new PointerURDFDragControls(
      scene,
      camera,
      renderer.domElement,
    );
    dragControlsRef.current = dragControls;
    dragControls.onHover = (joint) => {
      highlightLinkGeometry(joint, false);
      renderer.render(scene, camera);
    };
    dragControls.onUnhover = (joint) => {
      highlightLinkGeometry(joint, true);
      renderer.render(scene, camera);
    };
    dragControls.onClick = onJointClicked;

    return () => {
      if (containerRef.current) {
        containerRef.current.removeChild(renderer.domElement);
      }
      window.removeEventListener("resize", handleResize);
      updateOrientation("Z-up"); // Reset orientation on unmount
    };
  }, [urdfContent, files]);

  // Ensure that callbacks are updated as component is rerendered.
  useEffect(()=> {
    if (dragControlsRef.current !== null) {
      dragControlsRef.current!.onClick = onJointClicked
    }
  }, [onJointClicked])

  useEffect(() => {
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  return (
    <div className="flex flex-col lg:flex-row h-full relative">
      <div ref={containerRef} className="flex-grow h-[60vh] lg:h-auto" />
    </div>
  );
};

export default URDFRenderer;
