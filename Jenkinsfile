pipeline {
  agent { label 'unit-test' }

  environment {
    CI_IMAGE_NAME   = 'review-pytest'
    APP_IMAGE_NAME  = 'ale175/service-review'
    DOCKERHUB_CREDS = 'dockerhub-creds'
    INTEGRATION_JOB = 'peer-review-pipeline/integration-repo/main'
  }

  stages {
    stage('Build CI Image & Unit Tests') {
      steps {
        sh 'docker build -t "${CI_IMAGE_NAME}" -f ./test/Dockerfile.unit .'
        sh '''
          docker run --rm \
            --user "$(id -u)":"$(id -g)" \
            -e ENV="unit-test" \
            -v "${PWD}:/work" -w /work \
            "${CI_IMAGE_NAME}" sh -c 'pytest -v test/pytest && rm -rf .pytest_cache'
        '''
      }
    }

    stage('Build app image (:test)') {
      steps {
        script {
          docker.build("${APP_IMAGE_NAME}:test", "-f Dockerfile .")
        }
      }
    }

    stage('Push immagini di test (prima dell\'integrazione)') {
      steps {
        script {
          def shortSha = env.GIT_COMMIT ? env.GIT_COMMIT.take(7) : env.BUILD_NUMBER
          docker.withRegistry('https://index.docker.io/v1/', DOCKERHUB_CREDS) {
            // tag addizionale "test-<shortSha>" per tracciabilità
            sh "docker tag ${APP_IMAGE_NAME}:test ${APP_IMAGE_NAME}:test-${shortSha}"
            // push di ENTRAMBI i tag di test
            docker.image("${APP_IMAGE_NAME}:test").push()
            docker.image("${APP_IMAGE_NAME}:test-${shortSha}").push()
          }
        }
      }
    }

    stage('Trigger integrazione e attendi') {
      when {
        allOf {
          changeRequest()
          expression { return env.CHANGE_TARGET == 'main' }
        }
      }
      steps {
        script {
          build job: INTEGRATION_JOB,
                wait: true,
                propagate: true,
                parameters: [
                  string(name: 'SERVICE_NAME', value: 'review'),
                  string(name: 'TRIGGER_TYPE', value: 'single')
                ]
        }
      }
    }
  }

  post {
    success {
      echo '✅ OK: unit, push test, e integrazione (se PR→main) passati. Pubblico :last...'
      script {
        docker.withRegistry('https://index.docker.io/v1/', DOCKERHUB_CREDS) {
          // retag dell'immagine test come "last" e push
          sh "docker tag ${APP_IMAGE_NAME}:test ${APP_IMAGE_NAME}:last"
          docker.image("${APP_IMAGE_NAME}:last").push()
        }
      }
    }
    failure {
      echo '❌ KO: controlla i log (unit/build/push/integrazione).'
    }
    always {
      sh '''
        rm -rf .pytest_cache || true
        sudo chown -R $(id -u):$(id -g) . || true
      '''
      deleteDir()
    }
  }
}
