import { useEffect, useRef } from "react";
import * as THREE from "three";
import { getActions } from "../api.js";

// Fond 3D interactif : un champ de "bougies" boursieres flottant en
// profondeur. Il reagit a la souris (parallaxe), au scroll (rotation) et
// a l'humeur du marche (teinte verte si + de hausses, rouge si + de baisses).
// Optimise : pause hors-onglet, respect de prefers-reduced-motion, nettoyage
// complet des ressources GPU au demontage.

const NB_BOUGIES = 320;
const PROFONDEUR = 120; // etendue du champ en Z

// Couleurs de base et d'accent selon l'humeur du marche.
const BLEU = new THREE.Color("#3b82f6");
const VERT = new THREE.Color("#22c55e");
const ROUGE = new THREE.Color("#ef4444");
const NEUTRE = new THREE.Color("#64748b");

export default function Background3D() {
  const conteneurRef = useRef(null);

  useEffect(() => {
    const conteneur = conteneurRef.current;
    if (!conteneur) return undefined;

    const reduitMouvement = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    // --- Scene, camera, rendu ---------------------------------------
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2("#0b1220", 0.011);

    const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 400);
    camera.position.set(0, 0, 60);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setClearColor(0x000000, 0); // transparent : le degrade CSS transparait
    conteneur.appendChild(renderer.domElement);

    // Dimensionne depuis le conteneur (fixe, plein ecran). On evite ainsi le
    // bug ou window.innerWidth vaut 0 au tout premier montage (iframe, layout
    // pas encore calcule). Un ResizeObserver garde tout correct ensuite.
    function dimensionner() {
      const largeur = conteneur.clientWidth || window.innerWidth;
      const hauteur = conteneur.clientHeight || window.innerHeight;
      camera.aspect = largeur / hauteur;
      camera.updateProjectionMatrix();
      renderer.setSize(largeur, hauteur);
    }
    dimensionner();
    const observateur = new ResizeObserver(dimensionner);
    observateur.observe(conteneur);

    // --- Lumieres (leur couleur suivra l'humeur du marche) -----------
    const lumiereAmbiante = new THREE.AmbientLight(0x8899cc, 0.9);
    scene.add(lumiereAmbiante);
    const lumiereAccent = new THREE.PointLight(0x3b82f6, 180, 300);
    lumiereAccent.position.set(20, 30, 40);
    scene.add(lumiereAccent);

    // --- Champ de bougies (InstancedMesh, tres performant) -----------
    const geometrie = new THREE.BoxGeometry(0.6, 3, 0.6);
    const materiau = new THREE.MeshStandardMaterial({
      roughness: 0.35,
      metalness: 0.4,
      transparent: true,
      opacity: 0.85,
    });
    const bougies = new THREE.InstancedMesh(geometrie, materiau, NB_BOUGIES);
    bougies.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

    // Position, echelle et phase de bob de chaque bougie
    const bases = [];
    const dummy = new THREE.Object3D();
    const couleur = new THREE.Color();
    for (let i = 0; i < NB_BOUGIES; i++) {
      const base = {
        x: (Math.random() - 0.5) * 140,
        y: (Math.random() - 0.5) * 90,
        z: -Math.random() * PROFONDEUR,
        hauteur: 0.5 + Math.random() * 2.5,
        phase: Math.random() * Math.PI * 2,
        vitesse: 0.3 + Math.random() * 0.6,
      };
      bases.push(base);
      dummy.position.set(base.x, base.y, base.z);
      dummy.scale.set(1, base.hauteur, 1);
      dummy.updateMatrix();
      bougies.setMatrixAt(i, dummy.matrix);
      // Teinte initiale neutre : melange bleu/gris selon la profondeur
      couleur.copy(BLEU).lerp(NEUTRE, Math.random() * 0.5);
      bougies.setColorAt(i, couleur);
    }
    scene.add(bougies);

    // --- Humeur du marche : recolorer selon hausses/baisses ----------
    function appliquerHumeur(accent, force) {
      lumiereAccent.color.copy(accent);
      for (let i = 0; i < NB_BOUGIES; i++) {
        couleur.copy(BLEU).lerp(accent, Math.random() * force);
        bougies.setColorAt(i, couleur);
      }
      bougies.instanceColor.needsUpdate = true;
    }
    getActions()
      .then((actions) => {
        const hausses = actions.filter((a) => a.variation > 0).length;
        const baisses = actions.filter((a) => a.variation < 0).length;
        const total = hausses + baisses;
        if (!total) return;
        const ratio = hausses / total;
        if (ratio > 0.55) appliquerHumeur(VERT, (ratio - 0.5) * 1.6);
        else if (ratio < 0.45) appliquerHumeur(ROUGE, (0.5 - ratio) * 1.6);
      })
      .catch(() => {
        /* non connecte / backend absent : on garde la teinte neutre */
      });

    // --- Interactions : souris (parallaxe) + scroll (rotation) -------
    const souris = { x: 0, y: 0 };
    const cible = { x: 0, y: 0 };
    function onMouseMove(e) {
      cible.x = (e.clientX / window.innerWidth - 0.5) * 2;
      cible.y = (e.clientY / window.innerHeight - 0.5) * 2;
    }
    let rotationScroll = 0;
    function onScroll() {
      rotationScroll = window.scrollY * 0.0006;
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("scroll", onScroll, { passive: true });

    // --- Boucle d'animation -----------------------------------------
    const horloge = new THREE.Clock();
    let animationId = null;

    function rendreImage() {
      const t = horloge.getElapsedTime();

      // Parallaxe douce de la camera vers la souris
      souris.x += (cible.x - souris.x) * 0.04;
      souris.y += (cible.y - souris.y) * 0.04;
      camera.position.x = souris.x * 12;
      camera.position.y = -souris.y * 8;
      camera.lookAt(0, 0, -PROFONDEUR / 2);

      // Rotation lente du champ + influence du scroll
      bougies.rotation.z = t * 0.02 + rotationScroll;

      // Bob individuel de chaque bougie
      for (let i = 0; i < NB_BOUGIES; i++) {
        const b = bases[i];
        dummy.position.set(
          b.x,
          b.y + Math.sin(t * b.vitesse + b.phase) * 2,
          b.z
        );
        dummy.scale.set(1, b.hauteur, 1);
        dummy.rotation.z = Math.sin(t * b.vitesse * 0.5 + b.phase) * 0.15;
        dummy.updateMatrix();
        bougies.setMatrixAt(i, dummy.matrix);
      }
      bougies.instanceMatrix.needsUpdate = true;

      renderer.render(scene, camera);
      animationId = requestAnimationFrame(rendreImage);
    }

    if (reduitMouvement) {
      renderer.render(scene, camera); // une seule image statique
    } else {
      animationId = requestAnimationFrame(rendreImage);
    }

    // Pause quand l'onglet n'est pas visible (economie CPU/GPU/batterie)
    function onVisibilite() {
      if (document.hidden) {
        if (animationId) cancelAnimationFrame(animationId);
        animationId = null;
      } else if (!reduitMouvement && animationId === null) {
        horloge.getDelta(); // evite un saut de temps
        animationId = requestAnimationFrame(rendreImage);
      }
    }
    document.addEventListener("visibilitychange", onVisibilite);

    // --- Nettoyage : indispensable pour ne pas fuiter la memoire GPU -
    return () => {
      if (animationId) cancelAnimationFrame(animationId);
      observateur.disconnect();
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("visibilitychange", onVisibilite);
      geometrie.dispose();
      materiau.dispose();
      renderer.dispose();
      // Libere immediatement le contexte GPU : evite l'accumulation de
      // contextes WebGL (limite ~16 par navigateur) lors de demontages
      // rapides (StrictMode en dev, navigations frequentes).
      renderer.forceContextLoss();
      if (renderer.domElement.parentNode === conteneur) {
        conteneur.removeChild(renderer.domElement);
      }
    };
  }, []);

  return <div ref={conteneurRef} className="fond-3d" aria-hidden="true" />;
}
