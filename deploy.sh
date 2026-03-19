#!/bin/bash
# deploy.sh — run on VPS
set -e

ssh root@72.62.197.183 << 'EOF'
  mkdir -p /data/examsgen/{regulations/{CIT,VAT,PIT,FCT,TP,ADMIN,SHARED},syllabus,samples}
  cd /opt/examsgen
  git pull origin main
  docker build -t examsgen .
  docker stop examsgen 2>/dev/null; docker rm examsgen 2>/dev/null
  docker run -d \
    --name examsgen \
    --network coolify \
    --env-file /opt/examsgen/.env \
    -v /data/examsgen:/app/data \
    -p 8001:8000 \
    --label "traefik.enable=true" \
    --label "traefik.http.routers.examsgen.rule=Host(\`examsgen.gpt4vn.com\`)" \
    --label "traefik.http.routers.examsgen.tls.certresolver=letsencrypt" \
    --label "traefik.http.services.examsgen.loadbalancer.server.port=8000" \
    examsgen
  echo "Deployed!"
EOF
