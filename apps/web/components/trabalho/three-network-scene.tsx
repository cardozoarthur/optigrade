"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

type SceneMode = "air" | "university" | "comparison";

export function ThreeNetworkScene({ mode = "air" }: { mode?: SceneMode }) {
  const mountRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.set(0, 1.2, 7);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);
    const palette =
      mode === "air"
        ? ["#1b6b93", "#3f7d58", "#b26a00"]
        : mode === "university"
          ? ["#3f7d58", "#7c3aed", "#b26a00"]
          : ["#1b6b93", "#a33a4a", "#3f7d58"];

    const nodeGeometry = new THREE.SphereGeometry(0.12, 24, 24);
    const nodes = Array.from({ length: mode === "comparison" ? 12 : 16 }, (_, index) => {
      const angle = (index / (mode === "comparison" ? 12 : 16)) * Math.PI * 2;
      const radius = index % 3 === 0 ? 2.4 : index % 2 === 0 ? 1.65 : 2.05;
      const node = new THREE.Mesh(
        nodeGeometry,
        new THREE.MeshStandardMaterial({
          color: palette[index % palette.length],
          metalness: 0.24,
          roughness: 0.42
        })
      );
      node.position.set(Math.cos(angle) * radius, Math.sin(index * 0.9) * 0.55, Math.sin(angle) * radius);
      group.add(node);
      return node;
    });

    const lineMaterial = new THREE.LineBasicMaterial({ color: "#8da2b4", transparent: true, opacity: 0.34 });
    for (let index = 0; index < nodes.length; index += 1) {
      const current = nodes[index];
      const next = nodes[(index + 3) % nodes.length];
      const geometry = new THREE.BufferGeometry().setFromPoints([current.position, next.position]);
      group.add(new THREE.Line(geometry, lineMaterial));
    }

    const center = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.72, 1),
      new THREE.MeshStandardMaterial({
        color: mode === "comparison" ? "#17202a" : "#f6f8fb",
        emissive: mode === "comparison" ? "#1b6b93" : "#000000",
        emissiveIntensity: mode === "comparison" ? 0.18 : 0,
        metalness: 0.18,
        roughness: 0.36
      })
    );
    group.add(center);

    const light = new THREE.DirectionalLight("#ffffff", 2.2);
    light.position.set(3, 5, 4);
    scene.add(light);
    scene.add(new THREE.AmbientLight("#dce7ef", 1.4));

    let frame = 0;
    let animationId = 0;
    const resize = () => {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      renderer.setSize(width, height);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    };
    const animate = () => {
      frame += 0.01;
      group.rotation.y += 0.004;
      group.rotation.x = Math.sin(frame) * 0.06;
      nodes.forEach((node, index) => {
        node.scale.setScalar(1 + Math.sin(frame * 3 + index) * 0.12);
      });
      renderer.render(scene, camera);
      animationId = requestAnimationFrame(animate);
    };

    resize();
    animate();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animationId);
      mount.removeChild(renderer.domElement);
      renderer.dispose();
      nodeGeometry.dispose();
      lineMaterial.dispose();
    };
  }, [mode]);

  return <div ref={mountRef} className="h-full min-h-[260px] w-full" aria-hidden />;
}
