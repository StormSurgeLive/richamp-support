function [out]=trackll_2num(IN)    

A=IN;
sz=size(A);

c1=cell2mat(A(:,1));
c2=cell2mat(A(:,2));

for i=1:sz(1)
Ao(i,1)=(str2double(c1(i,1:3)))/10;
    Aon(i,1)=c1(i,4);    
        if(Aon(i,1)=='S')
            Ao(i,1)=-Ao(i,1);
        end

            cc=length(c2(i,:));
        
    Ao(i,2)=(str2double(c2(i,1:(cc-1))))/(.001*10^cc);

    Aoe(i,1)=c2(i,cc);
           if(Aoe(i,1)=='W')
            Ao(i,2)=-Ao(i,2);
           end
        
end

out=Ao;
end