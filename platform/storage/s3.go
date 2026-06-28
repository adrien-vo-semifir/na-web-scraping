package storage

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

// S3Sink écrit les objets dans un store compatible S3 (SeaweedFS en POC autonome,
// Ceph RGW en production — même API S3). L'endpoint est configurable pour viser un
// store self-host ; le path-style est activable (requis par la plupart des stores
// non-AWS).
//
// Configuration par environnement :
//
//	S3_BUCKET           bucket cible (défaut "raw")
//	S3_ENDPOINT         endpoint S3 (ex. http://localhost:8333) ; vide = AWS public
//	S3_REGION           région (défaut "us-east-1")
//	S3_ACCESS_KEY_ID    clé d'accès (sinon chaîne de credentials AWS par défaut)
//	S3_SECRET_ACCESS_KEY clé secrète
//	S3_USE_PATH_STYLE   "true" pour forcer le path-style (défaut true si endpoint custom)
type S3Sink struct {
	client *s3.Client
	bucket string
}

// NewS3Sink construit un S3Sink à partir de l'environnement. Il ne crée pas le bucket
// (supposé provisionné par l'infra) et n'effectue aucun appel réseau à la construction.
func NewS3Sink(ctx context.Context) (*S3Sink, error) {
	bucket := strings.TrimSpace(os.Getenv("S3_BUCKET"))
	if bucket == "" {
		bucket = "raw"
	}
	endpoint := strings.TrimSpace(os.Getenv("S3_ENDPOINT"))
	region := strings.TrimSpace(os.Getenv("S3_REGION"))
	if region == "" {
		region = "us-east-1"
	}

	loadOpts := []func(*awsconfig.LoadOptions) error{
		awsconfig.WithRegion(region),
	}

	// Credentials explicites si fournis par l'environnement ; sinon on laisse la
	// chaîne de credentials AWS par défaut opérer (profils, variables AWS_*, IAM…).
	accessKey := strings.TrimSpace(os.Getenv("S3_ACCESS_KEY_ID"))
	secretKey := strings.TrimSpace(os.Getenv("S3_SECRET_ACCESS_KEY"))
	if accessKey != "" && secretKey != "" {
		loadOpts = append(loadOpts, awsconfig.WithCredentialsProvider(
			credentials.NewStaticCredentialsProvider(accessKey, secretKey, ""),
		))
	}

	cfg, err := awsconfig.LoadDefaultConfig(ctx, loadOpts...)
	if err != nil {
		return nil, fmt.Errorf("storage(s3): chargement de la configuration AWS: %w", err)
	}

	// Path-style : requis pour SeaweedFS/Ceph RGW. Activé par défaut dès qu'un
	// endpoint custom est fourni, surchargeable via S3_USE_PATH_STYLE.
	usePathStyle := endpoint != ""
	if v := strings.TrimSpace(os.Getenv("S3_USE_PATH_STYLE")); v != "" {
		if b, perr := strconv.ParseBool(v); perr == nil {
			usePathStyle = b
		}
	}

	client := s3.NewFromConfig(cfg, func(o *s3.Options) {
		o.UsePathStyle = usePathStyle
		if endpoint != "" {
			o.BaseEndpoint = aws.String(endpoint)
		}
	})

	return &S3Sink{client: client, bucket: bucket}, nil
}

// Write dépose l'objet sous `key` dans le bucket et renvoie son URI s3://bucket/key.
// `meta` est attaché comme métadonnées utilisateur de l'objet S3 (x-amz-meta-*).
func (s *S3Sink) Write(key string, data []byte, contentType string, meta map[string]string) (string, error) {
	if s == nil || s.client == nil {
		return "", fmt.Errorf("storage(s3): client non initialisé")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	in := &s3.PutObjectInput{
		Bucket: aws.String(s.bucket),
		Key:    aws.String(strings.TrimLeft(key, "/")),
		Body:   bytes.NewReader(data),
	}
	if strings.TrimSpace(contentType) != "" {
		in.ContentType = aws.String(contentType)
	}
	if len(meta) > 0 {
		in.Metadata = meta
	}

	if _, err := s.client.PutObject(ctx, in); err != nil {
		return "", fmt.Errorf("storage(s3): PutObject %q dans %q: %w", key, s.bucket, err)
	}

	return fmt.Sprintf("s3://%s/%s", s.bucket, strings.TrimLeft(key, "/")), nil
}
