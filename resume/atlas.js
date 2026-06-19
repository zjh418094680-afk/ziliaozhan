const heroViewer = document.querySelector("#hero-viewer");
const workViewer = document.querySelector("#work-viewer");
const tabs = document.querySelectorAll(".work-switcher button");
const modelViewport = document.querySelector(".model-viewport");

function applyEngineeringMaterial(viewer, accent = false) {
  viewer.addEventListener("load", () => {
    (viewer.model?.materials || []).forEach((material) => {
      const pbr = material.pbrMetallicRoughness;
      pbr.setBaseColorFactor(accent ? [0.58, 0.22, 0.08, 1] : [0.52, 0.54, 0.54, 1]);
      pbr.setMetallicFactor(0.9);
      pbr.setRoughnessFactor(0.28);
    });
  });
}

applyEngineeringMaterial(heroViewer);
applyEngineeringMaterial(workViewer);

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((item) => {
      item.classList.toggle("active", item === tab);
      item.setAttribute("aria-selected", item === tab ? "true" : "false");
    });
    workViewer.dataset.accent = tab.dataset.id === "02" ? "true" : "false";
    workViewer.setAttribute("src", tab.dataset.model);
    document.querySelector("#work-number").textContent = tab.dataset.id;
    document.querySelector("#work-code").textContent = tab.dataset.code;
    document.querySelector("#model-code").textContent = tab.dataset.code;
  });
});

workViewer.addEventListener("load", () => {
  if (workViewer.dataset.accent !== "true") return;
  (workViewer.model?.materials || []).forEach((material) => {
    const pbr = material.pbrMetallicRoughness;
    pbr.setBaseColorFactor([0.58, 0.22, 0.08, 1]);
    pbr.setMetallicFactor(0.9);
    pbr.setRoughnessFactor(0.3);
  });
});

[heroViewer, workViewer].forEach((viewer) => {
  viewer.addEventListener("dblclick", () => {
    viewer.cameraOrbit = "0deg 75deg 105%";
    viewer.fieldOfView = "30deg";
  });
});

document.querySelector("#fullscreen-model").addEventListener("click", () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else modelViewport.requestFullscreen();
});

const sections = document.querySelectorAll(".section-observe");
const links = document.querySelectorAll(".rail nav a");
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    links.forEach((link) => {
      link.classList.toggle("active", link.getAttribute("href") === `#${entry.target.id}`);
    });
  });
}, {rootMargin: "-35% 0px -55% 0px"});

sections.forEach((section) => observer.observe(section));
