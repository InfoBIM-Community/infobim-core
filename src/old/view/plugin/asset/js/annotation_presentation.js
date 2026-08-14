(function (global) {
  "use strict";

  const payload = global.ontoBDCWorkStreamView;
  if (!payload || typeof payload !== "object") {
    throw new Error(
      "ontoBDCWorkStreamView must be available before annotation_presentation.js.",
    );
  }

  payload.annotationRuntime ||= {};
  payload.annotationRuntime.visual ||= {};
  payload.annotationRuntime.visual.theme = {
    colors: {
      theme: "#67e8f9",
      danger: "#fb7185",
      warning: "#f59e0b",
      success: "#22c55e",
      neutral: "#94a3b8",
      location: "#38bdf8",
    },
    borderTones: {
      light: "rgba(229, 238, 252, 0.82)",
      dark: "#07101d",
      theme: "#07101d",
    },
    fillOpacity: {
      solid: 0.9,
      transparent: 0.14,
      none: 0,
    },
  };

  payload.annotationRuntime.labels = Object.assign(
    {},
    payload.annotationRuntime.labels || {},
    {
      annotation: "Anotação",
      emptyAnnotation: "Anotação sem texto.",
      showAnnotation: "Exibir anotação: ",
      closeAnnotation: "Fechar anotação",
      categoryLabels: {
        NoteAnnotation: "Nota",
        IssueAnnotation: "Issue",
        ClassificationAnnotation: "Classificação",
        LocationAnnotation: "Localização",
        RecordAnnotation: "Registro",
      },
    },
  );
}(globalThis));
