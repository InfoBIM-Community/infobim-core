import * as THREE from "three";

export class BasisCurves {
    static create(attributes: Record<string, unknown>, material: THREE.LineBasicMaterial): THREE.Group {
        const points: unknown = attributes["usd::usdgeom::basiscurves::points"];
        if (!Array.isArray(points) || !points.every((point: unknown): boolean =>
            Array.isArray(point) && point.length === 3 && point.every(Number.isFinite))) {
            throw new Error("BasisCurves points must be finite XYZ triples.");
        }
        // IFCX documents predating curveVertexCounts describe one path per node.
        const declaredCounts: unknown = attributes["usd::usdgeom::basiscurves::curveVertexCounts"];
        const counts: unknown = declaredCounts === undefined ? [points.length] : declaredCounts;
        if (!Array.isArray(counts) || !counts.every((count: unknown): boolean =>
            typeof count === "number" && Number.isInteger(count) && count >= 2)
            || counts.reduce((sum: number, count: number): number => sum + count, 0) !== points.length) {
            throw new Error("BasisCurves curveVertexCounts must partition the points into paths.");
        }
        const type: unknown = attributes["usd::usdgeom::basiscurves::type"];
        if (type !== undefined && type !== "linear") {
            throw new Error("This viewer supports linear BasisCurves only; tessellate cubic curves first.");
        }
        const wrap: unknown = attributes["usd::usdgeom::basiscurves::wrap"];
        if (wrap !== undefined && wrap !== "periodic" && wrap !== "nonperiodic") {
            throw new Error("Unsupported BasisCurves wrap value.");
        }
        const group = new THREE.Group();
        let offset: number = 0;
        for (const count of counts) {
            const vertices: number[] = points.slice(offset, offset + count).flat();
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
            const line: THREE.Line = wrap === "periodic"
                ? new THREE.LineLoop(geometry, material)
                : new THREE.Line(geometry, material);
            group.add(line);
            offset += count;
        }
        return group;
    }
}
