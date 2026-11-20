#!/usr/bin/env python3
"""Build one self-contained offline HTML app (PDF engine + parser + UI)."""
import base64, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

pdfjs = open(os.path.join(HERE, 'pdf.min.js'), encoding='utf-8').read()
worker_b64 = base64.b64encode(open(os.path.join(HERE, 'pdf.worker.min.js'), 'rb').read()).decode()
parser = open(os.path.join(HERE, 'parser.js'), encoding='utf-8').read()
ui = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()

head, tail = ui.split('<script>\n(function(){', 1)
app = '(function(){' + tail

# Replace the server-dependent import block with fully local logic.
start = app.index('  function readFileB64(')
end = app.index('  render();\n  if(\'serviceWorker\'', start)
local_import = r'''  function readFileBuffer(file,cb){var r=new FileReader();r.onload=function(){cb(r.result);};r.readAsArrayBuffer(file);}
  var pdfTextCache={};
  function pdfText(buf,cb){
    pdfjsLib.getDocument({data:new Uint8Array(buf)}).promise.then(function(doc){
      var all=[];
      function next(p){
        if(p>doc.numPages){cb(all.join('\n'));return;}
        return doc.getPage(p).then(function(pg){return pg.getTextContent();}).then(function(tc){
          var lines=[],curY=null,cur='',lastH=11.5;
          tc.items.forEach(function(it){
            if(!it.str)return;
            var y=Math.round(it.transform[5]*10)/10, h=it.height||lastH;
            if(curY===null){cur=it.str;curY=y;lastH=h;return;}
            if(Math.abs(y-curY)>2){
              if(cur)lines.push(cur);
              var step=Math.max(6,h*1.5);
              var gap=Math.abs(curY-y),blanks=gap>100?0:Math.min(1,Math.max(0,Math.round(gap/step)-1));
              for(var bi=0;bi<blanks;bi++)lines.push('');
              cur=it.str;curY=y;lastH=h;
            }else{cur+=it.str;}
          });
          if(cur)lines.push(cur);
          all=all.concat(lines);
          return next(p+1);
        });
      }
      return next(1);
    }).catch(function(e){cb(null);});
  }
  function importFile(file,size,after){
    readFileBuffer(file,function(buf){
      if(pdfTextCache[file.name+file.lastModified]&&size===0&&after.sizeZero){
        after.sizeZero(pdfTextCache[file.name+file.lastModified]);return;
      }
      pdfText(buf.slice(0),function(text){
        if(text===null){after.fail('Could not read this PDF.');return;}
        try{
          var isEnglish=/^\s*(Round|Row)\s+\d+/im.test(text);
          var probe=KnitParser.parse(text,0);
          if(isEnglish){var eng=KnitParser.parseEnglish(text,0);if(eng)probe=eng;}
          var count=probe.size_count||KnitParser.sizeCount(text)||1;
          if(after.sizeCount)after.sizeCount(count);
          if(probe.error){if(after.chart){after.chart(buf,probe.error);}else after.fail(probe.error);return;}
          var selected=(size===0)?probe:(isEnglish?(KnitParser.parseEnglish(text,size)||probe):KnitParser.parse(text,size));
          after.ok(selected);
        }catch(e){after.fail('Pattern error: '+e.message);}
      });
    });
  }
  document.getElementById('pdfFile').addEventListener('change',function(){
    var file=this.files[0];if(!file)return;
    var sel=document.getElementById('size');sel.innerHTML='<option value="0">Size 1</option>';
    msg('Reading PDF on this device…');
    importFile(file,0,{
      sizeCount:function(c){
        if(c>1){var h='';for(var i=0;i<c;i++)h+='<option value="'+i+'">Size '+(i+1)+'</option>';sel.innerHTML=h;}
      },
      ok:function(){msg('Ready — choose a size, then click Import PDF.');},
      fail:function(e){msg(e,true);}
    });
  });
  document.getElementById('importPdf').addEventListener('click',function(){
    var file=document.getElementById('pdfFile').files[0];
    if(!file){msg('Choose a PDF file first.',true);return;}
    msg('Importing on this device…');
    var size=parseInt(document.getElementById('size').value||'0',10);
    importFile(file,size,{
      ok:function(d){loadPattern(d);msg('Imported '+d.row_count+' rows from '+d.title+'.');},
      fail:function(e){msg(e,true);},
      chart:function(buf,err){
        function jpegUrl(buffer){
          var u=new Uint8Array(buffer),starts=[],ends=[],i;
          for(i=0;i<u.length-1;i++){if(u[i]===0xff&&u[i+1]===0xd8)starts.push(i);if(u[i]===0xff&&u[i+1]===0xd9)ends.push(i+1);}
          var best=null;
          starts.forEach(function(a){for(var k=0;k<ends.length;k++){var b=ends[k];if(b>a&&(!best||b-a>best[1]-best[0]))best=[a,b];}});
          return best?new Blob([u.slice(best[0],best[1])],{type:'image/jpeg'}):null;
        }
        var rpr=parseInt(prompt('How many rows in one chart repeat?','19'),10)||19;
        var reps=parseInt(prompt('How many times is the chart repeated?','18'),10)||18;
        var sts=parseInt(prompt('How many stitches across the chart?','64'),10)||64;
        var blob=jpegUrl(buf);
        if(!blob){msg('Could not find a chart image in this PDF.',true);return;}
        var fr=new FileReader();
        fr.onload=function(){var img=fr.result;
        var groups=[],n=0,total=rpr*reps;
        for(var k=0;k<total;k+=8){var steps=[];
          for(var z=0;z<8&&k+z<total;z++){n++;var repn=Math.floor((n-1)/rpr)+1,ir=((n-1)%rpr)+1;
            steps.push({label:String(n),instruction:'Follow chart row '+ir+' of '+rpr+' (repeat '+repn+' of '+reps+')',tags:['chart'],stitches:sts});}
          groups.push({name:'Rows '+(k+1)+'–'+(k+steps.length),steps:steps});}
        loadPattern({title:'Chart pattern',note:rpr+'-row chart · '+reps+' repeats · '+sts+' stitches',groups:groups,chart:{img:img,rowsPerRepeat:rpr}});
        msg('Chart loaded: '+total+' rows. The green band marks the current chart row.');
        };fr.readAsDataURL(blob);
      }
    });
  });

'''
app = app[:start] + local_import + app[end:]

engine = ('<script id="pdfWorkerSrc" type="text/plain">' + worker_b64 + '</script>\n'
          '<script>' + pdfjs + '</script>\n'
          '<script>' + parser + '</script>\n'
          '<script>\n'
          'var __wb=document.getElementById("pdfWorkerSrc").textContent.trim(),__bin=atob(__wb),'
          '__u8=new Uint8Array(__bin.length);for(var __i=0;__i<__bin.length;__i++)__u8[__i]=__bin.charCodeAt(__i);'
          'pdfjsLib.GlobalWorkerOptions.workerSrc=URL.createObjectURL(new Blob([__u8],{type:"text/javascript"}));'
          '</script>\n')

out = head + engine + '<script>\n' + app
# app already ends with </script></body></html> from original tail
open(os.path.join(ROOT, 'StitchRow-offline.html'), 'w', encoding='utf-8').write(out)
print('wrote', os.path.join(ROOT, 'StitchRow-offline.html'), len(out), 'bytes')
