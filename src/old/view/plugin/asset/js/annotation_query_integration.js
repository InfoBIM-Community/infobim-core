(function (global) {
  "use strict";
  const workspaceButton=document.getElementById("open-annotation-workspace");
  const subjectButton=document.getElementById("open-subject-page");
  const dialog=document.getElementById("annotation-query-dialog");
  const host=document.getElementById("annotation-query-host");
  let containerHandle=null;
  function runtime(){if(!global.OntoBDCWorkStreamAnnotations)throw new Error("OntoBDC annotation runtime is unavailable.");return global.OntoBDCWorkStreamAnnotations;}
  function context(){return {containerHandle:containerHandle};}
  function show(){if(typeof dialog.showModal==="function")dialog.showModal();else dialog.setAttribute("open","");}
  document.addEventListener("infobim:project-opened",function(event){containerHandle=event.detail.containerHandle;workspaceButton.disabled=false;subjectButton.disabled=false;});
  workspaceButton.addEventListener("click",async function(){show();host.textContent="Carregando anotações…";try{await runtime().openWorkspace(host,context(),{labels:{total:"Total",openIssues:"Issues abertas",withoutGeometry:"Sem geometria",withoutSubject:"Sem assunto",open:"Abrir"}});}catch(error){host.textContent="Não foi possível abrir as anotações: "+error.message;}});
  subjectButton.addEventListener("click",async function(){show();host.textContent="Carregando assuntos…";try{await runtime().openSubjectPage(host,context(),null,{labels:{space:"Espaço",timeline:"Linha do tempo",people:"Pessoas",unassigned:"Sem assunto atribuído",withoutPosition:"Sem posição espacial",empty:"Nenhuma anotação."}});}catch(error){host.textContent="Não foi possível abrir os assuntos: "+error.message;}});
  dialog.querySelector("[data-close-query]").addEventListener("click",function(){dialog.close();});
}(globalThis));
