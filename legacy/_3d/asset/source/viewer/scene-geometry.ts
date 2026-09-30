import * as THREE from "three";

export type SceneSummary = {drawings: number; meshes: number; curves: number; pointClouds: number};

export class SceneGeometry {
    static measure(scene: THREE.Object3D, drawings: number): SceneSummary {
        const summary: SceneSummary = {drawings, meshes: 0, curves: 0, pointClouds: 0};
        scene.traverse((object: THREE.Object3D): void => {
            if (!(object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points)) return;
            const positions: THREE.BufferAttribute | THREE.InterleavedBufferAttribute | undefined = object.geometry.getAttribute("position");
            if (positions === undefined || positions.count === 0) return;
            if (object instanceof THREE.Mesh) summary.meshes++;
            else if (object instanceof THREE.Line) summary.curves++;
            else summary.pointClouds++;
        });
        const bounds: THREE.Box3 = new THREE.Box3().setFromObject(scene);
        if (summary.meshes + summary.curves + summary.pointClouds === 0 || bounds.isEmpty()) {
            throw new Error("The IFCX drawings contain no visible geometry. Nothing was loaded.");
        }
        if (![...bounds.min.toArray(), ...bounds.max.toArray()].every(Number.isFinite)) {
            throw new Error("The IFCX drawings contain non-finite geometry or transforms.");
        }
        return summary;
    }

    static describe(summary: SceneSummary): string {
        return `${summary.drawings} IFCX drawing(s): ${summary.curves} curve(s), ${summary.meshes} mesh(es), ${summary.pointClouds} point cloud(s).`;
    }
}
