// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// three 挂载层：场景装配 + 渲染循环 + 轨道控制 + 拾取 + 选中高亮 + 视角复位。
// 本文件是移植单元——只依赖 three 与 ifcLoader 的序列化结果（IfcMeshData），
// 不依赖 React/router/store（选中状态经 handle 回调上浮，由组件层桥接 zustand）。
// 形态刻意保持「裸 three 对象 + 薄 handle」：移植到 R3F 目标仓时可直接
// <primitive object={scene}> 或按 handle 能力逐项搬用。

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { IfcMeshData } from "./ifcLoader";

export interface IfcSceneHandle {
  addMesh(mesh: IfcMeshData): void;
  fitToBoundingBox(): void;
  /** null 清除高亮；返回拾取到的 expressID（画布点击由组件层转发）。 */
  pick(clientX: number, clientY: number): number | null;
  setSelection(expressID: number | null): void;
  dispose(): void;
}

const SELECT_COLOR = 0x3b82f6;

export function mountIfcScene(canvas: HTMLCanvasElement): IfcSceneHandle {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf0f2f5);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
  camera.position.set(10, 10, 10);
  camera.lookAt(0, 0, 0);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(canvas.clientWidth || 1, canvas.clientHeight || 1, false);

  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dir = new THREE.DirectionalLight(0xffffff, 1.2);
  dir.position.set(1, 2, 1);
  scene.add(dir);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;

  // expressID → meshes（一个构件可有多个 placed geometry，高亮整组）
  const byExpress = new Map<number, THREE.Mesh[]>();
  const originalColors = new Map<THREE.Mesh, THREE.Color>();

  let raf = 0;
  const loop = () => {
    controls.update();
    renderer.render(scene, camera);
    raf = requestAnimationFrame(loop);
  };
  raf = requestAnimationFrame(loop);

  const resize = () => {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
  };
  const observer = new ResizeObserver(resize);
  observer.observe(canvas);

  const raycaster = new THREE.Raycaster();

  return {
    addMesh(mesh: IfcMeshData) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(mesh.positions, 3));
      geometry.setIndex(new THREE.BufferAttribute(mesh.indices, 1));
      geometry.computeBoundingSphere();
      const material = new THREE.MeshLambertMaterial({
        color: new THREE.Color(mesh.color.x, mesh.color.y, mesh.color.z),
        side: THREE.DoubleSide,
      });
      const object = new THREE.Mesh(geometry, material);
      object.matrixAutoUpdate = false;
      object.matrix.fromArray(mesh.transform);
      object.userData.expressID = mesh.expressID;
      scene.add(object);
      const group = byExpress.get(mesh.expressID) ?? [];
      group.push(object);
      byExpress.set(mesh.expressID, group);
      originalColors.set(object, material.color.clone());
    },
    fitToBoundingBox() {
      const box = new THREE.Box3();
      for (const group of byExpress.values()) {
        for (const m of group) {
          m.geometry.computeBoundingBox();
          if (m.geometry.boundingBox) box.union(m.geometry.boundingBox);
        }
      }
      if (box.isEmpty()) return;
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const radius = Math.max(size.x, size.y, size.z) / 2 || 1;
      controls.target.copy(center);
      const dirVec = new THREE.Vector3(1, 0.8, 1).normalize();
      camera.position.copy(center).addScaledVector(dirVec, radius * 3);
      camera.lookAt(center);
      camera.near = radius / 100;
      camera.far = radius * 100;
      camera.updateProjectionMatrix();
    },
    pick(clientX: number, clientY: number) {
      const rect = canvas.getBoundingClientRect();
      const pointer = new THREE.Vector2(
        ((clientX - rect.left) / rect.width) * 2 - 1,
        -((clientY - rect.top) / rect.height) * 2 + 1
      );
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(scene.children, false);
      for (const hit of hits) {
        const id = hit.object.userData.expressID;
        if (typeof id === "number") return id;
      }
      return null;
    },
    setSelection(expressID: number | null) {
      for (const [mesh, color] of originalColors) {
        // 高亮不改原色：恢复用记录值（Map 迭代期间不增删，安全）
        (mesh.material as THREE.MeshLambertMaterial).color.copy(color);
      }
      if (expressID == null) return;
      const group = byExpress.get(expressID);
      if (!group) return;
      const highlight = new THREE.Color(SELECT_COLOR);
      for (const mesh of group) {
        (mesh.material as THREE.MeshLambertMaterial).color.copy(highlight);
      }
    },
    dispose() {
      cancelAnimationFrame(raf);
      observer.disconnect();
      controls.dispose();
      for (const group of byExpress.values()) {
        for (const mesh of group) {
          mesh.geometry.dispose();
          (mesh.material as THREE.Material).dispose();
        }
      }
      renderer.dispose();
    },
  };
}
