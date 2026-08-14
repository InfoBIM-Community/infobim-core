(function (global) {
  "use strict";

  const state = { resources: [], people: [] };

  function searchable(items, query, type) {
    const needle=String(query||"").trim().toLocaleLowerCase();
    return items.filter(item=>!needle||String(item.label||item.name||item.uri||item.path||"").toLocaleLowerCase().includes(needle)).map(item=>({
      uri:String(item.uri||item.id||item.path),
      label:String(item.label||item.name||item.path||item.uri||item.id),
      description:item.description||null,
      type:type,
      metadata:Object.assign({},item)
    }));
  }

  const resolver=global.OntoBDCEntityResolver.create({
    search:async function(query,context){
      const kind=context&&context.kind;
      if(kind==="person")return searchable(state.people,query,"Person");
      if(kind==="subject")return [];
      return searchable(state.resources,query,"Resource");
    },
    resolve:async function(uri){
      const item=state.resources.concat(state.people).find(value=>String(value.uri||value.id||value.path)===uri);
      return item?{uri:uri,label:item.label||item.name||item.path||uri,description:item.description||null,type:item.type||null,metadata:item}:null;
    }
  });

  function setResources(resources){state.resources=Array.isArray(resources)?resources.slice():[];}
  function setPeople(people){state.people=Array.isArray(people)?people.slice():[];}

  global.InfoBIMAnnotationEntityResolver=Object.freeze({resolver:resolver,setResources:setResources,setPeople:setPeople});
}(globalThis));
