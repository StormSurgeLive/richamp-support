function [x,y,depth,element,nn_new]=subset_dontplot_mesh(grd,xrng,yrng)
% function [x,y,depth,element,nn_new]=subset_dontplot_mesh(grd,xrng,yrng)
% subset mesh, but do not plot

% find nodes within bounding box
i=find( grd.x >= xrng(1) & grd.x <= xrng(2) & grd.y >= yrng(1) & grd.y <= yrng(2) );
x=grd.x(i); y=grd.y(i); depth=grd.dp(i);
% vector of length equal to number of nodes in full mesh with values equal
% to the new node numbers
nn_new=nan*ones(size(grd.x));
nn_new(i)=[1:length(i)];

% get corresponding element connectivity
j=find( grd.x(grd.nm) >= xrng(1) & grd.x(grd.nm) <= xrng(2) & grd.y(grd.nm) >= yrng(1) & grd.y(grd.nm) <= yrng(2) );

im=zeros(size(grd.nm));
im(j)=1;
nnode=sum(im')';
k=find(nnode == 3 );    % selects elements totally within bounding box
element=grd.nm(k,:);
element=nn_new(element);
