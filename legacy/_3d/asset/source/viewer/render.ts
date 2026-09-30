// (C) buildingSMART International
// published under MIT license 

import { ComposedObject } from './composed-object';
import { IfcxFile } from '../ifcx-core/schema/schema-helper';
import { compose3 } from './compose-flattened';
import { ENVIRONMENT_HDR_DATA_URI } from './environment-hdr.generated';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { PCDLoader } from 'three/addons/loaders/PCDLoader.js';
import { BasisCurves } from './basis-curves';
import { SceneGeometry, SceneSummary } from './scene-geometry';

let controls, renderer, scene, camera;
type datastype = [string, IfcxFile][];
let datas: datastype = [];
let autoCamera = true;
let animationStarted: boolean = false;


let objectMap: { [path: string]: any } = {};
let domMap: { [path: string]: HTMLElement } = {};
let primMap: { [path: string]: ComposedObject } = {};
let currentPathMapping: any = null;
let rootPrim: ComposedObject | null = null;

let selectedPaths: Set<string> = new Set();
let anchorPath: string | null = null;
let orderedPaths: string[] = [];

let projectName: string | null = null;

type TreeTab = 'model' | 'attributes';
let activeTreeTab: TreeTab = 'model';
let lastSelection: { prim: ComposedObject; pathMapping: any; root: any } | null = null;

// A tree node either the Model tree or the Selection attributes tab can
// render, sharing the same .tree-node/.tree-toggle/.tree-children DOM
// shape (and so the same collapse/expand-all buttons) without either one
// needing to know about the other's data. label is a plain string for the
// common case, or a builder for the one case that needs richer markup: a
// clickable reference link.
type LabeledTreeNode = {
    label: string | (() => Node);
    children?: LabeledTreeNode[];
};

type ProjectTreeNode = {
    name: string;
    kind: string;
    children?: ProjectTreeNode[];
};

// A leaf of ThreeDElementTree carries its own parsed IFCX document
// alongside its file name: the offline viewer has no way to fetch a
// file by path once it is launched (everything reaches this page
// through the same one-shot bootstrap JSON the whole page loads from),
// so a click has to load what is already in hand, not fetch anything.
type ThreeDElementTreeNode = {
    name: string;
    kind?: string;
    children?: ThreeDElementTreeNode[];
    file_name?: string;
    document?: IfcxFile;
};

type InspectTab = 'project' | 'three_d';
let activeInspectTab: InspectTab = 'project';
let projectInspectTreeData: unknown = null;
let threeDInspectTreeData: unknown = null;

export function setProjectName(name: string | null): void {
    projectName = name;
}

function projectRootLabel(): string {
    return projectName === null ? "IfcProject" : `IfcProject (${projectName})`;
}


let raycaster = new THREE.Raycaster();
let mouse = new THREE.Vector2();

var envMap;

let darkTheme: boolean = false;

export function setDarkTheme(dark: boolean): void {
    darkTheme = dark;
    if (scene) {
        scene.background = dark ? new THREE.Color(0x000000) : null;
        const defaultLineColor = dark ? 0xffffff : 0x000000;
        scene.traverse((group: any) => {
            // defaultLineColor is set on the Group BasisCurves.create()
            // returns, but the material lives on its Line/LineLoop
            // children, so each flagged group needs its own inner
            // traversal to reach them.
            if (!group.userData.defaultLineColor) return;
            group.traverse((o: any) => {
                const mat = o.material;
                if (!mat || !mat.color) return;
                // an object mid-selection keeps its true color stashed in
                // _origColor while material.color shows the highlight instead;
                // update that stash so the theme color still applies once
                // the object is deselected, rather than the color it had
                // when it was last selected.
                if (o.userData._origColor) {
                    o.userData._origColor = new THREE.Color(defaultLineColor);
                } else {
                    mat.color.set(defaultLineColor);
                }
            });
        });
    }
    document.body.classList.toggle('dark', dark);
}

async function init() {
    scene = new THREE.Scene();
    scene.background = darkTheme ? new THREE.Color(0x000000) : null;

    // lights
    const ambient = new THREE.AmbientLight(0xddeeff, 0.4);
    scene.add(ambient);
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.0);
    keyLight.position.set(5, -10, 7.5);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.5);
    fillLight.position.set(-5, 5, 5);
    scene.add(fillLight);
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.3);
    rimLight.position.set(0, 8, -10);
    scene.add(rimLight);

    const nd: HTMLElement | null = document.querySelector('.viewport');
    if (nd === null || nd.clientWidth === 0 || nd.clientHeight === 0) {
        throw new Error("The viewer viewport has no usable size.");
    }
    camera = new THREE.PerspectiveCamera(75, nd.clientWidth / nd.clientHeight, 0.1, 100);

    camera.up.set(0, 0, 1);
    camera.position.set(50, 50, 50);
    camera.lookAt(0, 0, 0);

    renderer = new THREE.WebGLRenderer({
        alpha: true,
        logarithmicDepthBuffer: true
    });

    // for GLTF PBR rendering, create environment map using PMREMGenerator:
    // see https://threejs.org/docs/#api/en/extras/PMREMGenerator
    
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    pmremGenerator.compileEquirectangularShader();
    new RGBELoader()
        .load(ENVIRONMENT_HDR_DATA_URI, function (texture) {
            envMap = pmremGenerator.fromEquirectangular(texture).texture;
            
            // uncomment to also show the skybox on screen, instead of only in PBR reflections:
            //scene.background = envMap;
            //scene.backgroundRotation.x = 0.5 * Math.PI
            scene.environment = envMap;
    
            texture.dispose();
            pmremGenerator.dispose();
        });

    //@ts-ignore
    renderer.setSize(nd.offsetWidth, nd.offsetHeight);

    //@ts-ignore
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.25;

    nd!.appendChild(renderer.domElement);
    renderer.domElement.addEventListener('click', onCanvasClick);
    renderer.domElement.addEventListener('dblclick', onCanvasDoubleClick);

    return scene;
}

function HasAttr(node: ComposedObject | undefined, attrName: string)
{
    if (!node || !node.attributes) return false;
    return !!node.attributes[attrName];
}

function FindChildWithAttr(node: ComposedObject | undefined, attrName: string)
{
    if (!node || !node.children) return undefined;
    for (let i = 0; i < node.children.length; i++)
    {
        if (HasAttr(node.children[i], attrName))
        {
            return node.children[i];
        }
    }

    return undefined;
}

function setHighlight(obj: any, highlight: boolean) {
    if (!obj) return;
    obj.traverse((o) => {
        const mat = o.material;
        if (mat && mat.color) {
            if (highlight) {
                if (!o.userData._origColor) {
                    o.userData._origColor = mat.color.clone();
                }
                o.material = mat.clone();
                o.material.color.set(0xff0000);
            } else if (o.userData._origColor) {
                mat.color.copy(o.userData._origColor);
                delete o.userData._origColor;
            }
        }
    });
}

type SelectionMode = 'replace' | 'toggle' | 'range';

function selectionModeFromEvent(event: MouseEvent): SelectionMode {
    if (event.shiftKey) return 'range';
    if (event.ctrlKey || event.metaKey) return 'toggle';
    return 'replace';
}

function applySelection(paths: Set<string>) {
    for (const path of selectedPaths) {
        if (paths.has(path)) continue;
        const obj = objectMap[path];
        const dom = domMap[path];
        if (obj) setHighlight(obj, false);
        if (dom) dom.classList.remove('selected');
    }
    for (const path of paths) {
        if (selectedPaths.has(path)) continue;
        const obj = objectMap[path];
        const dom = domMap[path];
        if (obj) setHighlight(obj, true);
        if (dom) dom.classList.add('selected');
    }
    selectedPaths = paths;
}

function selectPath(path: string | null, mode: SelectionMode = 'replace') {
    if (!path) {
        applySelection(new Set());
        anchorPath = null;
        return;
    }

    if (mode === 'toggle') {
        const next = new Set(selectedPaths);
        if (next.has(path)) {
            next.delete(path);
        } else {
            next.add(path);
        }
        applySelection(next);
        anchorPath = path;
        return;
    }

    if (mode === 'range' && anchorPath) {
        const start = orderedPaths.indexOf(anchorPath);
        const end = orderedPaths.indexOf(path);
        if (start !== -1 && end !== -1) {
            const [lo, hi] = start <= end ? [start, end] : [end, start];
            applySelection(new Set(orderedPaths.slice(lo, hi + 1)));
            return;
        }
    }

    applySelection(new Set([path]));
    anchorPath = path;
}

function onCanvasClick(event: MouseEvent) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(Object.values(objectMap), true);
    if (intersects.length > 0) {
        let obj = intersects[0].object;
        while (obj && !obj.userData.path) obj = obj.parent;
        if (obj && obj.userData.path) {
            const path = obj.userData.path;
            const prim = primMap[path];
            if (prim) {
                handleClick(prim, currentPathMapping, rootPrim || prim);
            }
            selectPath(path, selectionModeFromEvent(event));
        }
    }
    else {
        selectPath(null);
    }
}

function onCanvasDoubleClick(event: MouseEvent): void {
    // A double click on the canvas asks where in the model it landed, so
    // a command can be told to place something there. What is under the
    // cursor answers first, because a point on a drawing or on a solid is
    // a point someone aimed at; with nothing under it, the ray is met by
    // the ground plane of the model, which is what a click on the empty
    // sky of an otherwise horizontal view means.
    const rect: DOMRect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);

    const intersects = raycaster.intersectObjects(Object.values(objectMap), true);
    const point: THREE.Vector3 | null = intersects.length > 0
        ? intersects[0].point.clone()
        : groundPoint();
    if (point === null) {
        return;
    }

    // The scene is the model: the camera is Z up and every node carries
    // the transform its own layer declares, so what comes back here is
    // already in the coordinates the IFC model is written in, and needs
    // no conversion to be handed to a command.
    renderer.domElement.dispatchEvent(new CustomEvent('infobim:point-picked', {
        bubbles: true,
        detail: { x: point.x, y: point.y, z: point.z },
    }));
}

function groundPoint(): THREE.Vector3 | null {
    // The model's own ground, z = 0, not a plane facing the camera: a
    // point picked on it keeps meaning the same place when the view
    // turns, which a plane that follows the camera would not.
    const ground: THREE.Plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    const point: THREE.Vector3 = new THREE.Vector3();

    return raycaster.ray.intersectPlane(ground, point) === null ? null : point;
}

function tryCreateMeshGltfMaterial(path: ComposedObject[]) {

    // check for PBR defined by the gltf::material schema
    for (let p of path) {
        if (!p.attributes) {
            continue;
        }
        const pbrMetallicRoughness = p.attributes["gltf::material::pbrMetallicRoughness"];
        const normalTexture = p.attributes["gltf::material::normalTexture"];
        const occlusionTexture = p.attributes["gltf::material::occlusionTexture"];
        const emissiveTexture = p.attributes["gltf::material::emissiveTexture"];
        const emissiveFactor = p.attributes["gltf::material::emissiveFactor"];
        const alphaMode = p.attributes["gltf::material::alphaMode"];
        const alphaCutoff = p.attributes["gltf::material::alphaCutoff"];
        const doubleSided = p.attributes["gltf::material::doubleSided"];
        if (!pbrMetallicRoughness && !normalTexture && !occlusionTexture && !emissiveTexture && !emissiveFactor && !alphaMode && !alphaCutoff && !doubleSided) {
            // if none of the gltf::material properties are defined, we don't use pbr rendering, but default to the bsi::ifc::presentation definitions
            continue;
        }

        // otherwise, we know that we want a PBR material. If a property is null, we use the default defined by the gltf specification:
        // see https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#reference-material

        let material = new THREE.MeshStandardMaterial();

        // define defaults:
        material.color = new THREE.Color(1.0, 1.0, 1.0);
        material.metalness = 1.0;
        material.roughness = 1.0;
        
        // note that not all GLTF properties are converted here yet to the THREE.MeshStandardMaterial PBR material, 
        // such as reading the texture URLs or from base64, this should be added. 

        if (pbrMetallicRoughness) {
            let baseColorFactor = pbrMetallicRoughness["baseColorFactor"];
            if (baseColorFactor) {
                material.color = new THREE.Color(baseColorFactor[0], baseColorFactor[1], baseColorFactor[2]);
            }

            let metallicFactor = pbrMetallicRoughness["metallicFactor"];
            if (metallicFactor !== undefined) {
                material.metalness = metallicFactor;
            }

            let roughnessFactor = pbrMetallicRoughness["roughnessFactor"];
            if (roughnessFactor !== undefined) {
                material.roughness = roughnessFactor;
            }
        }
        material.envMap = envMap
        material.needsUpdate = true
        material.envMapRotation = new THREE.Euler(0.5 * Math.PI, 0, 0);
        // console.log(material)
        return material;
    }

    return undefined
}

function createMaterialFromParent(path: ComposedObject[]) {
    let material = {
        color: new THREE.Color(0.6, 0.6, 0.6),
        transparent: false,
        opacity: 1
    };
    for (let p of path) {
        const color = p.attributes ? p.attributes["bsi::ifc::presentation::diffuseColor"] : null;
        if (color) {
        material.color = new THREE.Color(...color);
        const opacity = p.attributes["bsi::ifc::presentation::opacity"];
        if (opacity) {
            material.transparent = true;
            material.opacity = opacity;
        }
        break;
        }
    }
    return material;
}

function createCurveFromJson(path: ComposedObject[]) {
  const hasExplicitColor: boolean = path.some((p): boolean =>
      Boolean(p.attributes && p.attributes["bsi::ifc::presentation::diffuseColor"]));
  const material = createMaterialFromParent(path);
  let lineMaterial = new THREE.LineBasicMaterial({ ...material });
  lineMaterial.color = hasExplicitColor
      ? lineMaterial.color.multiplyScalar(0.8)
      : new THREE.Color(darkTheme ? 0xffffff : 0x000000);
  const curve = BasisCurves.create(path[0].attributes, lineMaterial);
  // a curve with no explicit diffuseColor is drawn in the theme's own
  // ink color, not a fixed one, so setDarkTheme can find and flip it
  // when the theme changes after this curve already exists.
  if (!hasExplicitColor) {
      curve.userData.defaultLineColor = true;
  }
  return curve;
}

function createMeshFromJson(path: ComposedObject[]) {
  let points = new Float32Array(path[0].attributes["usd::usdgeom::mesh::points"].flat());
  let indices = new Uint32Array(path[0].attributes["usd::usdgeom::mesh::faceVertexIndices"]);
  
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(points, 3));
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  geometry.computeVertexNormals();
  
  
  var meshMaterial;
  
  let gltfPbrMaterial = tryCreateMeshGltfMaterial(path);
  if (gltfPbrMaterial) {
    meshMaterial = gltfPbrMaterial
    // console.log(meshMaterial)
  } else {
    const m = createMaterialFromParent(path);
    meshMaterial = new THREE.MeshLambertMaterial({ ...m });
  }

  return new THREE.Mesh(geometry, meshMaterial);
}

// functions for creating point clouds
function createPointsFromJsonPcdBase64(path: ComposedObject[]) {
    const base64_string = path[0].attributes["pcd::base64"];
    const decoded = atob(base64_string);
    const len = decoded.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = decoded.charCodeAt(i);
    }
    const loader = new PCDLoader();
    const points = loader.parse(bytes.buffer);
    points.material.sizeAttenuation = false;
    points.material.size = 2;
    return points;
}

function createPoints(geometry: THREE.BufferGeometry, withColors: boolean): THREE.Points {
    const material = new THREE.PointsMaterial();
    material.sizeAttenuation = false;
    material.fog = true;
    material.size = 5;
    material.color = new THREE.Color(withColors ? 0xffffff : 0x000000);

    if (withColors) {
        material.vertexColors = true;
    }
    return new THREE.Points(geometry, material);
}

function createPointsFromJsonArray(path: ComposedObject[]) {
    const geometry = new THREE.BufferGeometry();

    const positions = new Float32Array(path[0].attributes["points::array::positions"].flat());
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));

    const colors = path[0].attributes["points::array::colors"];
    if (colors) {
        const colors_ = new Float32Array(colors.flat());
        geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors_, 3));
    }
    return createPoints(geometry, colors);
}

function base64ToArrayBuffer(str): ArrayBuffer | undefined {
    let binary;
    try {
        binary = atob(str);
    }
    catch(e) {
        throw new Error("base64 encoded string is invalid");
    }
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; ++i) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}

function createPointsFromJsonPositionBase64(path: ComposedObject[]) {
    const geometry = new THREE.BufferGeometry();

    const positions_base64 = path[0].attributes["points::base64::positions"];
    const positions_bytes = base64ToArrayBuffer(positions_base64);
    if (!positions_bytes) {
        return null;
    }
    const positions = new Float32Array(positions_bytes!);
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    
    const colors_base64 = path[0].attributes["points::base64::colors"];
    if (colors_base64) {
        const colors_bytes = base64ToArrayBuffer(colors_base64);
        if (colors_bytes) {
            const colors = new Float32Array(colors_bytes!);
            geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
        }
    }
    return createPoints(geometry, colors_base64);
}

function traverseTree(path: ComposedObject[], parent, pathMapping) {
    const node = path[0];
    let elem: any = new THREE.Group();
    if (HasAttr(node, "usd::usdgeom::visibility::visibility"))
    {
        if (node.attributes["usd::usdgeom::visibility::visibility"] === 'invisible') {
            return;
        }
    }
    if (HasAttr(node, "usd::usdgeom::mesh::points"))
    {
        elem = createMeshFromJson(path);
    } 
    else if (HasAttr(node, "usd::usdgeom::basiscurves::points"))
    {
        elem = createCurveFromJson(path);
    }
    // point cloud data types:
    else if (HasAttr(node, "pcd::base64"))
    {
        elem = createPointsFromJsonPcdBase64(path);
    }
    else if (HasAttr(node, "points::array::positions"))
    {
        elem = createPointsFromJsonArray(path);
    }
    else if (HasAttr(node, "points::base64::positions"))
    {
        elem = createPointsFromJsonPositionBase64(path);
    }
    
    objectMap[node.name] = elem;
    primMap[node.name] = node;
    orderedPaths.push(node.name);
    elem.userData.path = node.name;

    for (let path of Object.entries(node.attributes || {}).filter(([k, _]) => k.startsWith('__internal_')).map(([_, v]) => v)) {
      (pathMapping[String(path)] = pathMapping[String(path)] || []).push(node.name);
    }

    parent.add(elem);
    if (path.length > 1) {
        elem.matrixAutoUpdate = false;

        let matrixNode = node.attributes && node.attributes['usd::xformop::transform'] ? node.attributes['usd::xformop::transform'].flat() : null;
        if (matrixNode) {
            let matrix = new THREE.Matrix4();
            //@ts-ignore
            matrix.set(...matrixNode);
            matrix.transpose();
            elem.matrix = matrix;
        }
    }

    (node.children || []).forEach(child => traverseTree([child, ...path], elem || parent, pathMapping));
}

const icons = {
    'usd::usdgeom::mesh::points': 'deployed_code', 
    'usd::usdgeom::basiscurves::points': 'line_curve',
    'usd::usdshade::material::outputs::surface.connect': 'line_style',
    'pcd::base64': 'grain',
    'points::array::positions': 'grain',
    'points::base64::positions': 'grain',
};

function handleClick(prim: ComposedObject, pathMapping: any, root: any) {
  lastSelection = { prim, pathMapping, root: root || prim };
  if (activeTreeTab === 'attributes') {
    renderAttributesTab();
  }
}

// Turns one attribute value into the tree node(s) it renders as. An array
// or a plain object becomes a branch -- its own children, expandable and
// collapsible like every other tree node on this page -- instead of the
// inline "(a,b,c)" text a flat attributes table used to squeeze it into.
// A resolvable reference stays a single clickable leaf, exactly as it
// behaved before this was a tree.
function attributeValueToTreeNode(
  key: string,
  value: any,
  pathMapping: any,
  root: any,
): LabeledTreeNode {
  if (Array.isArray(value)) {
    return {
      label: key,
      children: value.map((item, index) => attributeValueToTreeNode(
        `[${index}]`, item, pathMapping, root,
      )),
    };
  }

  if (value !== null && typeof value === "object") {
    const ks = Object.keys(value);
    if (ks.length === 1 && ks[0] === "ref" && pathMapping[value.ref] && pathMapping[value.ref].length === 1) {
      const resolvedRefAsPath: string = pathMapping[value.ref][0];
      return {
        label: () => {
          const fragment: DocumentFragment = document.createDocumentFragment();
          fragment.appendChild(document.createTextNode(`${key}: `));
          const link: HTMLAnchorElement = document.createElement("a");
          link.className = "tree-ref-link";
          link.setAttribute("href", "#");
          link.textContent = resolvedRefAsPath;
          link.onclick = (event: MouseEvent) => {
            event.preventDefault();
            let referenced: ComposedObject | null = null;
            const recurse = (n: ComposedObject) => {
              if (n.name === resolvedRefAsPath) {
                referenced = n;
              } else {
                (n.children || []).forEach(recurse);
              }
            };
            recurse(root);
            if (referenced) {
              handleClick(referenced, pathMapping, root);
            }
          };
          fragment.appendChild(link);
          return fragment;
        },
      };
    }

    return {
      label: key,
      children: Object.entries(value).map(([k, v]) => attributeValueToTreeNode(
        k, v, pathMapping, root,
      )),
    };
  }

  return { label: `${key}: ${String(value)}` };
}

function attributesToTree(prim: ComposedObject, pathMapping: any, root: any): LabeledTreeNode[] {
  const entries: [string, any][] = Object.entries(prim.attributes || {}).filter(
    ([key]) => !key.startsWith("__internal_"),
  );
  return [
    { label: `name: ${prim.name}` },
    ...entries.map(([key, value]) => attributeValueToTreeNode(key, value, pathMapping, root)),
  ];
}

function renderAttributesTab(): void {
  const container: HTMLElement | null = document.querySelector<HTMLElement>(".tree");
  if (container === null) {
    return;
  }

  container.innerHTML = "";
  if (lastSelection === null) {
    const empty: HTMLElement = document.createElement("p");
    empty.textContent = "Click an element to see its attributes.";
    container.appendChild(empty);
    return;
  }

  attributesToTree(lastSelection.prim, lastSelection.pathMapping, lastSelection.root)
    .forEach((node) => buildLabeledDomTree(node, container, []));
}

function renderModelTab(): void {
  const container: HTMLElement | null = document.querySelector<HTMLElement>(".tree");
  if (container === null) {
    return;
  }

  container.innerHTML = "";
  if (rootPrim !== null) {
    buildDomTree(rootPrim, container, currentPathMapping || {}, null, []);
  }
}

// Scoped to [data-tree-tab] rather than the shared .tree-tab class: the
// Project inspect / 3D inspect tab pair below reuses that same class for
// identical styling, and a selector keyed on the class alone would also
// match (and wrongly clear the active state of) those other buttons.
function setActiveTabButton(tab: TreeTab): void {
  document.querySelectorAll<HTMLButtonElement>("[data-tree-tab]").forEach((button) => {
    const isActive: boolean = button.dataset.treeTab === tab;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
}

export function activateModelTab(): void {
  activeTreeTab = "model";
  setActiveTabButton("model");
  renderModelTab();
}

export function activateAttributesTab(): void {
  activeTreeTab = "attributes";
  setActiveTabButton("attributes");
  renderAttributesTab();
}

function projectTreeToLabeledTree(node: ProjectTreeNode): LabeledTreeNode {
  return {
    label: node.name,
    children: (node.children || []).map(projectTreeToLabeledTree),
  };
}

function isNamedTreeNode(value: unknown): value is { name: string } {
  return (
    typeof value === "object"
    && value !== null
    && typeof (value as { name: unknown }).name === "string"
  );
}

// Loads one 3D-inspect element into the scene exactly as the manual
// "IFCX drawings" file picker would: the same ViewerModels.add call,
// the same status line on success or failure (see createLayerDom,
// which reports the same way for the picker's own layer controls).
function loadThreeDElement(fileName: string, document_: IfcxFile): void {
  ViewerModels.add([[fileName, document_]]).then((summary: SceneSummary): void => {
    document.getElementById('status')!.textContent = SceneGeometry.describe(summary);
  }).catch((error: unknown): void => {
    document.getElementById('status')!.textContent = error instanceof Error ? error.message : String(error);
  });
}

// A leaf that carries a document becomes a clickable link -- loading it
// into "IFCX drawings" the moment it is clicked, the same as if the
// element had been picked and submitted through the manual file input.
// A branch (or a leaf missing its document, e.g. a *.ifc-3d element) is
// just a label: nothing this page knows how to load without a fetch it
// cannot make.
function threeDElementTreeToLabeledTree(node: ThreeDElementTreeNode): LabeledTreeNode {
  const children: ThreeDElementTreeNode[] = node.children || [];
  if (children.length === 0 && node.file_name !== undefined && node.document !== undefined) {
    const fileName: string = node.file_name;
    const document_: IfcxFile = node.document;
    const title: string = node.name;
    return {
      label: (): Node => {
        const link: HTMLAnchorElement = document.createElement("a");
        link.className = "tree-ref-link";
        link.setAttribute("href", "#");
        link.textContent = title;
        link.title = `Double-click to load ${fileName} into IFCX drawings`;
        // Double-click, matching buildDomTree's own convention (a single
        // click there selects/highlights; a double-click is the bigger,
        // deliberate action -- there requesting the element's IFC drawing,
        // here loading it). A single click here still needs to swallow the
        // anchor's default '#' navigation, since two single clicks fire
        // before the dblclick event does.
        link.onclick = (event: MouseEvent): void => {
          event.preventDefault();
        };
        link.ondblclick = (event: MouseEvent): void => {
          event.preventDefault();
          loadThreeDElement(fileName, document_);
        };
        return link;
      },
    };
  }

  return {
    label: node.name,
    children: children.map(threeDElementTreeToLabeledTree),
  };
}

// Project inspect and 3D inspect share one container (.inspect-tree) the
// same way Model tree and Selection attributes share .tree: only one
// tab's content exists in the DOM at a time, rebuilt from whichever
// data belongs to the active tab.
function renderInspectTab(): void {
  const container: HTMLElement | null = document.querySelector<HTMLElement>(".inspect-tree");
  if (container === null) {
    return;
  }

  container.innerHTML = "";
  if (activeInspectTab === "three_d") {
    if (!isNamedTreeNode(threeDInspectTreeData)) {
      const empty: HTMLElement = document.createElement("p");
      empty.textContent = "No 3D elements were found for this Project.";
      container.appendChild(empty);
      return;
    }
    buildLabeledDomTree(
      threeDElementTreeToLabeledTree(threeDInspectTreeData as ThreeDElementTreeNode),
      container,
      [],
    );
    return;
  }

  if (!isNamedTreeNode(projectInspectTreeData)) {
    const empty: HTMLElement = document.createElement("p");
    empty.textContent = "No project inspect data available.";
    container.appendChild(empty);
    return;
  }
  buildLabeledDomTree(
    projectTreeToLabeledTree(projectInspectTreeData as ProjectTreeNode),
    container,
    [],
  );
}

// Scoped to [data-inspect-tab] for the same reason setActiveTabButton is
// scoped to [data-tree-tab]: both tab pairs share the .tree-tab class
// for identical styling, so a class-only selector here would also touch
// (and wrongly toggle) the Model tree / Selection attributes buttons.
function setActiveInspectTabButton(tab: InspectTab): void {
  document.querySelectorAll<HTMLButtonElement>("[data-inspect-tab]").forEach((button) => {
    const isActive: boolean = button.dataset.inspectTab === tab;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
}

export function activateProjectInspectTab(): void {
  activeInspectTab = "project";
  setActiveInspectTabButton("project");
  renderInspectTab();
}

export function activateThreeDInspectTab(): void {
  activeInspectTab = "three_d";
  setActiveInspectTabButton("three_d");
  renderInspectTab();
}

export function renderProjectInspectTree(tree: unknown): void {
  projectInspectTreeData = tree;
  renderInspectTab();
}

export function renderThreeDInspectTree(tree: unknown): void {
  threeDInspectTreeData = tree;
  renderInspectTab();
}

function connectorPrefix(ancestry: boolean[]): string {
    // ancestry[i] says whether the ancestor at that depth was the last
    // child of its own parent -- true draws blank continuation space
    // under it (nothing left to connect further down), false draws a
    // vertical bar (a sibling still follows, so the line must continue).
    const continuation: string = ancestry
        .slice(0, -1)
        .map((isLast) => (isLast ? '    ' : '│   '))
        .join('');
    if (ancestry.length === 0) {
        return '';
    }
    const own: string = ancestry[ancestry.length - 1] ? '└── ' : '├── ';
    return continuation + own;
}

// The generic half of what buildDomTree does for the Model tree: the
// connector/toggle/children DOM shape and the collapse-on-build default,
// with no prim-specific concerns (icons, 3D selection, double-click) --
// shared by the Selection attributes tab and the Project inspect panel,
// which have nothing to select or highlight, just a label and children.
function buildLabeledDomTree(node: LabeledTreeNode, container: HTMLElement, ancestry: boolean[]): void {
    const treeNode: HTMLElement = document.createElement('div');
    treeNode.className = 'tree-node';

    const row: HTMLElement = document.createElement('div');
    row.className = 'tree-row';

    const connector: HTMLElement = document.createElement('span');
    connector.className = 'tree-connector';
    connector.textContent = connectorPrefix(ancestry);
    row.appendChild(connector);

    const children: LabeledTreeNode[] = node.children || [];
    const toggle: HTMLElement = document.createElement('span');
    toggle.className = children.length > 0 ? 'tree-toggle' : 'tree-toggle tree-toggle-empty';
    toggle.textContent = children.length > 0 ? '▸' : '';
    row.appendChild(toggle);

    const labelSpan: HTMLElement = document.createElement('span');
    if (typeof node.label === 'string') {
        labelSpan.appendChild(document.createTextNode(node.label));
    } else {
        labelSpan.appendChild(node.label());
    }
    row.appendChild(labelSpan);

    treeNode.appendChild(row);

    if (children.length > 0) {
        const childrenNode: HTMLElement = document.createElement('div');
        childrenNode.className = 'tree-children';
        childrenNode.hidden = true;
        children.forEach((child, index) => buildLabeledDomTree(
            child,
            childrenNode,
            [...ancestry, index === children.length - 1],
        ));
        treeNode.appendChild(childrenNode);

        toggle.onclick = (evt: MouseEvent) => {
            evt.stopPropagation();
            const collapsed: boolean = !childrenNode.hidden;
            childrenNode.hidden = collapsed;
            toggle.textContent = collapsed ? '▸' : '▾';
        };
    }

    container.appendChild(treeNode);
}

function buildDomTree(prim, node, pathMapping, root: any, ancestry: boolean[]) {
    const treeNode: HTMLElement = document.createElement('div');
    treeNode.className = 'tree-node';

    const row: HTMLElement = document.createElement('div');
    row.className = 'tree-row';

    const connector: HTMLElement = document.createElement('span');
    connector.className = 'tree-connector';
    connector.textContent = connectorPrefix(ancestry);
    row.appendChild(connector);

    const children: ComposedObject[] = prim.children || [];
    const toggle: HTMLElement = document.createElement('span');
    toggle.className = children.length > 0 ? 'tree-toggle' : 'tree-toggle tree-toggle-empty';
    toggle.textContent = children.length > 0 ? '▸' : '';
    row.appendChild(toggle);

    const label: unknown = prim.attributes?.['infobim::name'];
    if (label !== undefined && typeof label !== 'string') {
        throw new Error(`Invalid drawing name on IFCX node ${prim.name}`);
    }
    const labelSpan: HTMLElement = document.createElement('span');
    labelSpan.appendChild(document.createTextNode(
        label === undefined
            ? (prim.name === '' ? projectRootLabel() : prim.name.split('/').reverse()[0])
            : label
    ));
    row.appendChild(labelSpan);

    const iconSpan: HTMLElement = document.createElement('span');
    Object.entries(icons).forEach(([k, v]) => iconSpan.innerText += (prim.attributes || {})[k] ? v : ' ');
    iconSpan.className = "material-symbols-outlined";
    row.appendChild(iconSpan);

    domMap[prim.name] = row;
    row.dataset.path = prim.name;
    row.onclick = (evt: MouseEvent) => {
        handleClick(prim, pathMapping, root || prim);
        selectPath(prim.name, selectionModeFromEvent(evt));
        evt.stopPropagation();
    };
    row.ondblclick = (event: MouseEvent): void => {
        event.stopPropagation();
        if (event.target instanceof Element && event.target.closest('.tree-toggle')) {
            return;
        }
        const globalId: unknown = prim.attributes?.['infobim::globalId'];
        row.dispatchEvent(new CustomEvent('infobim:element-requested', {
            bubbles: true,
            detail: { globalId },
        }));
    };
    treeNode.appendChild(row);

    if (children.length > 0) {
        const childrenNode: HTMLElement = document.createElement('div');
        childrenNode.className = 'tree-children';
        // every tree starts fully collapsed; a viewer opens the branches
        // it actually wants, rather than scrolling past everything else.
        childrenNode.hidden = true;
        children.forEach((child, index) => buildDomTree(
            child,
            childrenNode,
            pathMapping,
            root || prim,
            [...ancestry, index === children.length - 1],
        ));
        treeNode.appendChild(childrenNode);

        toggle.onclick = (evt: MouseEvent) => {
            evt.stopPropagation();
            const collapsed: boolean = !childrenNode.hidden;
            childrenNode.hidden = collapsed;
            toggle.textContent = collapsed ? '▸' : '▾';
        };
    }

    node.appendChild(treeNode);
}

function setTreeCollapsed(collapsed: boolean): void {
    document.querySelectorAll<HTMLElement>('.tree .tree-children').forEach((el) => {
        el.hidden = collapsed;
    });
    document.querySelectorAll<HTMLElement>('.tree .tree-toggle:not(.tree-toggle-empty)').forEach((el) => {
        el.textContent = collapsed ? '▸' : '▾';
    });
}

export function collapseTree(): void {
    setTreeCollapsed(true);
}

export function expandTree(): void {
    setTreeCollapsed(false);
}

export async function composeAndRender(): Promise<SceneSummary> {
    if (scene) {
        // @todo does this actually free up resources?
        // retain only the lights
        scene.children = scene.children.filter(n => n instanceof THREE.Light);
    }

    objectMap = {};
    domMap = {};
    primMap = {};
    orderedPaths = [];
    selectedPaths = new Set();
    anchorPath = null;
    currentPathMapping = null;
    rootPrim = null;
    lastSelection = null;

    if (datas.length === 0) {
        activateModelTab();
        return {drawings: 0, meshes: 0, curves: 0, pointClouds: 0};
    }

    let tree: null | ComposedObject = null;
    let dataArray = datas.map(arr => arr[1]);
    
    tree = await compose3(dataArray as IfcxFile[]);
    if (!tree) {
        throw new Error("IFCX composition produced no model tree.");
    }

    if (!scene) {
        await init()
    }

    let pathMapping = {};
    traverseTree([tree], scene, pathMapping);
    const summary: SceneSummary = SceneGeometry.measure(scene, datas.length);
    currentPathMapping = pathMapping;
    rootPrim = tree;

    if (autoCamera) {
        const boundingBox = new THREE.Box3();
        boundingBox.setFromObject(scene);
        if (!boundingBox.isEmpty()) {
            let avg = boundingBox.min.clone().add(boundingBox.max).multiplyScalar(0.5);
            let ext = boundingBox.max.clone().sub(boundingBox.min).length();
            camera.position.copy(avg.clone().add(new THREE.Vector3(0,-Math.SQRT2,1).normalize().multiplyScalar(ext)));
            camera.near = Math.max(ext / 10000, 0.000001);
            camera.far = Math.max(ext * 10, camera.near * 100);
            camera.updateProjectionMatrix();
            controls.target.copy(avg);
            controls.update();
            
            // only on first successful load
            autoCamera = false;
        }
    }

    activateModelTab();
    if (!animationStarted) {
        animationStarted = true;
        animate();
    }
    return summary;
}

function createLayerDom() {
    document.querySelector('.layers div')!.innerHTML = '';
    datas.forEach(([name, _], index) => {
        const elem = document.createElement('div');
        elem.appendChild(document.createTextNode(name));
        ['\u25B3', '\u25BD', '\u00D7'].reverse().forEach((lbl, cmd) => {
            const btn = document.createElement('span');
            btn.onclick = (evt) => {
                evt.stopPropagation();
                if (cmd === 2) {
                    if (index > 0) {
                        [datas[index], datas[index - 1]] = [datas[index - 1], datas[index]];
                    }
                } else if (cmd === 1) {
                    if (index < datas.length - 1) {
                        [datas[index], datas[index + 1]] = [datas[index + 1], datas[index]];
                    }
                } else if (cmd === 0) {
                    datas.splice(index, 1);
                }
                composeAndRender().then((summary: SceneSummary): void => {
                    createLayerDom();
                    document.getElementById('status')!.textContent = SceneGeometry.describe(summary);
                }).catch((error: unknown): void => {
                    document.getElementById('status')!.textContent = error instanceof Error ? error.message : String(error);
                });
            }
            btn.appendChild(document.createTextNode(lbl));
            elem.appendChild(btn);
        });
        document.querySelector('.layers div')!.appendChild(elem);
    });
}

export class ViewerModels {
    static async add(models: [string, IfcxFile][]): Promise<SceneSummary> {
        if (models.length === 0) throw new Error("No IFCX drawings were supplied.");
        const ids: Set<string> = new Set(datas.map((entry): string => entry[1].header.id));
        for (const [name, model] of models) {
            if (!model || typeof model.header?.id !== "string" || !model.header.id
                || !Array.isArray(model.data) || !Array.isArray(model.imports)
                || typeof model.schemas !== "object" || model.schemas === null) {
                throw new Error(`Invalid IFCX document: ${name}`);
            }
            if (ids.has(model.header.id)) throw new Error(`Duplicate IFCX layer ID: ${model.header.id}`);
            ids.add(model.header.id);
        }
        const previous: datastype = datas;
        datas = [...datas, ...models];
        try {
            autoCamera = true;
            const summary: SceneSummary = await composeAndRender();
            createLayerDom();
            return summary;
        } catch (error) {
            datas = previous;
            throw error;
        }
    }
}

function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}
