clear all
clc
[EToV,VX,B,opedat,boudat,title] = readfort14('fort.14',1);



 OB_ID=opedat.nbdv;

 WW3_mesh_generator(EToV,VX(:,2),VX(:,3),B,OB_ID,'EGOM.msh',1);